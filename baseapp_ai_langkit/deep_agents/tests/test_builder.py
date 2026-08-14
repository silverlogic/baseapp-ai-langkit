"""Unit tests for deep-agent construction (no DB, no LLM, no graph).

``build_deep_agent`` is the single construction point for every surface, so these
tests pin its contract: what the caller passes reaches ``create_deep_agent``, the
governor middleware is always built and never removable, and a surface without an
answer schema builds a valid agent anyway.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel

from baseapp_ai_langkit.deep_agents import builder
from baseapp_ai_langkit.deep_agents.limits import (
    DeepAgentLimits,
    HardLimitsMiddleware,
    PlanningLoopMiddleware,
    RunBudget,
)
from baseapp_ai_langkit.deep_agents.tool_scoping import ExcludedToolsMiddleware


class _StubAnswer(BaseModel):
    text: str


class _StubLLM:
    """Stand-in language model; construction never calls it."""


def _build(**kwargs) -> MagicMock:
    """Run build_deep_agent with create_deep_agent patched; return the mock."""
    create_deep_agent = MagicMock(name="create_deep_agent")
    with patch("deepagents.create_deep_agent", create_deep_agent):
        builder.build_deep_agent(model=_StubLLM(), tools=kwargs.pop("tools", []), **kwargs)
    return create_deep_agent


class BuildDeepAgentTests(SimpleTestCase):
    def test_caller_tools_and_prompt_reach_the_agent(self):
        tool = MagicMock(name="tool")
        call = _build(tools=[tool], system_prompt="be careful").call_args.kwargs
        self.assertEqual(call["tools"], [tool])
        self.assertEqual(call["system_prompt"], "be careful")

    def test_governors_are_always_built_and_ordered(self):
        middleware = _build().call_args.kwargs["middleware"]
        self.assertIsInstance(middleware[0], ModelCallLimitMiddleware)
        self.assertIsInstance(middleware[1], HardLimitsMiddleware)
        self.assertIsInstance(middleware[2], PlanningLoopMiddleware)

    def test_limits_profile_sizes_the_governors(self):
        limits = DeepAgentLimits(
            max_model_calls=7, soft_token_budget=11, finalize_tools=frozenset({"emit"})
        )
        middleware = _build(limits=limits).call_args.kwargs["middleware"]
        self.assertEqual(middleware[1].soft_token_budget, 11)
        self.assertEqual(middleware[1].finalize_tools, frozenset({"emit"}))

    def test_response_format_is_wrapped_and_named_for_the_governor(self):
        call = _build(response_format=_StubAnswer).call_args.kwargs
        self.assertIsInstance(call["response_format"], ToolStrategy)
        self.assertIs(call["response_format"].schema, _StubAnswer)
        self.assertEqual(call["middleware"][1].structured_tool_name, "_StubAnswer")

    def test_an_already_wrapped_schema_is_not_wrapped_twice(self):
        strategy = ToolStrategy(schema=_StubAnswer)
        call = _build(response_format=strategy).call_args.kwargs
        self.assertIs(call["response_format"], strategy)

    def test_no_response_format_leaves_the_governor_without_a_structured_tool(self):
        """A surface whose result is written by tools has no answer to validate."""
        call = _build().call_args.kwargs
        self.assertIsNone(call["response_format"])
        self.assertIsNone(call["middleware"][1].structured_tool_name)

    def test_skills_root_is_advertised_only_when_the_surface_has_skills(self):
        self.assertEqual(_build().call_args.kwargs["skills"], [])
        self.assertEqual(_build(has_skills=True).call_args.kwargs["skills"], ["/skills/"])

    def test_excluded_tools_add_a_middleware_after_the_governors(self):
        middleware = _build(excluded_tools=["ls"]).call_args.kwargs["middleware"]
        self.assertIsInstance(middleware[-1], ExcludedToolsMiddleware)
        self.assertEqual(middleware[-1].excluded, frozenset({"ls"}))

    def test_no_excluded_tools_adds_no_middleware(self):
        middleware = _build().call_args.kwargs["middleware"]
        self.assertFalse(any(isinstance(m, ExcludedToolsMiddleware) for m in middleware))

    def test_extra_middleware_lands_last(self):
        extra = AgentMiddleware()
        middleware = _build(excluded_tools=["ls"], extra_middleware=[extra]).call_args.kwargs[
            "middleware"
        ]
        self.assertIs(middleware[-1], extra)
        self.assertIsInstance(middleware[-2], ExcludedToolsMiddleware)

    def test_the_budget_reaches_the_governors(self):
        budget = RunBudget()
        middleware = _build(budget=budget).call_args.kwargs["middleware"]
        self.assertIs(middleware[1].budget, budget)


class SubagentTests(SimpleTestCase):
    """What happens to a declared subagent spec on its way to ``create_deep_agent``."""

    def _spec(self, **extra) -> dict:
        return {"name": "surveyor", "description": "reads pages", "system_prompt": "go", **extra}

    def test_no_subagents_passes_none_rather_than_an_empty_list(self):
        self.assertIsNone(_build().call_args.kwargs["subagents"])

    def test_a_declared_spec_reaches_the_agent_with_its_own_fields_intact(self):
        tool = MagicMock(name="read_document")
        spec = self._spec(tools=[tool])
        passed = _build(subagents=[spec]).call_args.kwargs["subagents"]
        self.assertEqual(passed[0]["name"], "surveyor")
        self.assertEqual(passed[0]["tools"], [tool])

    def test_the_governors_are_injected_into_the_spec(self):
        """A subagent without them is an ungoverned run: nothing counts its spend."""
        middleware = _build(subagents=[self._spec()]).call_args.kwargs["subagents"][0]["middleware"]
        self.assertIsInstance(middleware[0], ModelCallLimitMiddleware)
        self.assertIsInstance(middleware[1], HardLimitsMiddleware)
        self.assertIsInstance(middleware[2], PlanningLoopMiddleware)
        self.assertFalse(middleware[1].is_root)

    def test_the_subagent_governors_share_the_roots_budget(self):
        budget = RunBudget()
        call = _build(subagents=[self._spec()], budget=budget).call_args.kwargs
        self.assertIs(call["middleware"][1].budget, budget)
        self.assertIs(call["subagents"][0]["middleware"][1].budget, budget)

    def test_the_specs_own_middleware_runs_after_the_governors(self):
        own = AgentMiddleware()
        middleware = _build(subagents=[self._spec(middleware=[own])]).call_args.kwargs["subagents"][
            0
        ]["middleware"]
        self.assertIs(middleware[-1], own)

    def test_the_caller_never_has_its_spec_mutated(self):
        spec = self._spec()
        _build(subagents=[spec])
        self.assertNotIn("middleware", spec)

    def test_a_compiled_subagent_is_passed_through_untouched(self):
        """Its middleware was decided when it was compiled; there is nothing to add to."""
        spec = {"name": "prebuilt", "description": "d", "runnable": MagicMock()}
        passed = _build(subagents=[spec]).call_args.kwargs["subagents"][0]
        self.assertNotIn("middleware", passed)

    def test_a_remote_subagent_is_passed_through_untouched(self):
        spec = {"name": "remote", "description": "d", "graph_id": "other-deployment"}
        passed = _build(subagents=[spec]).call_args.kwargs["subagents"][0]
        self.assertNotIn("middleware", passed)


class ExtractAnswerTests(SimpleTestCase):
    def test_returns_the_parsed_instance(self):
        answer = _StubAnswer(text="hi")
        self.assertIs(builder.extract_answer({"structured_response": answer}, _StubAnswer), answer)

    def test_coerces_a_mapping(self):
        parsed = builder.extract_answer({"structured_response": {"text": "hi"}}, _StubAnswer)
        self.assertEqual(parsed, _StubAnswer(text="hi"))

    def test_never_fabricates_an_answer(self):
        self.assertIsNone(builder.extract_answer({}, _StubAnswer))
        self.assertIsNone(builder.extract_answer({"structured_response": {}}, _StubAnswer))
        self.assertIsNone(builder.extract_answer({"structured_response": "text"}, _StubAnswer))


class ContentHelperTests(SimpleTestCase):
    def test_stringify_handles_text_blocks(self):
        content = [{"type": "text", "text": "one"}, {"type": "image"}, "two"]
        self.assertEqual(builder.stringify_content(content), "one\ntwo")

    def test_extract_last_text_prefers_the_last_ai_message(self):
        messages = [
            MagicMock(type="ai", content="first"),
            MagicMock(type="human", content="question"),
            MagicMock(type="ai", content="second"),
        ]
        self.assertEqual(builder.extract_last_text(messages), "second")

    def test_extract_last_text_returns_empty_when_there_is_none(self):
        self.assertEqual(builder.extract_last_text([MagicMock(type="human", content="q")]), "")
