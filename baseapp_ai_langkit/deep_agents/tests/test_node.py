"""Tests for the deep-agent node: its error contract, its telemetry, and a real run.

The last class runs the real deepagents graph over :class:`ScriptedChatModel`, which is
the level every consumer of this runtime needs: a gate or a completion rule is a
statement about what happens when the model does a specific thing, and scripting is
the only cheap way to make it do that thing.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.deep_agents import builder
from baseapp_ai_langkit.deep_agents import node as node_module
from baseapp_ai_langkit.deep_agents.limits import (
    DeepAgentLimitError,
    DeepAgentLimits,
    DeepAgentTimeoutError,
)
from baseapp_ai_langkit.deep_agents.node import DeepAgentNodeError, LangGraphDeepAgent
from baseapp_ai_langkit.deep_agents.skills.sources import (
    FilesystemSkillSource,
    SkillDocument,
)
from baseapp_ai_langkit.deep_agents.testing import (
    RecordedCalls,
    ScriptedChatModel,
    ScriptedTurn,
)


class _StubAnswer(BaseModel):
    text: str


@tool
def search_document(query: str) -> str:
    """Search the document for a phrase."""
    return f"found {query} on page 2"


@tool
def emit_deals(count: int) -> str:
    """Record the deals found in the document."""
    return f"accepted {count} deals"


class _Node(LangGraphDeepAgent):
    run_name = "test_agent"

    def get_agent_tools(self):
        return [search_document, emit_deals]


def _node(model=None, **attrs) -> _Node:
    node = _Node(llm=model or MagicMock(), config={})
    for name, value in attrs.items():
        setattr(node, name, value)
    return node


class ErrorContractTests(SimpleTestCase):
    """The contract every caller of this runtime branches on."""

    def _failing_node(self, exc: Exception) -> _Node:
        node = _node()
        agent = MagicMock()
        agent.invoke.side_effect = exc
        node._agent = agent
        return node

    def test_a_limit_error_propagates_untouched(self):
        original = DeepAgentTimeoutError("out of time")
        node = self._failing_node(original)
        with self.assertLogs(node_module.logger, level="ERROR"):
            with self.assertRaises(DeepAgentTimeoutError) as caught:
                node.invoke([HumanMessage("go")])
        self.assertIs(caught.exception, original)

    def test_the_library_call_limit_normalizes_into_the_limit_family(self):
        node = self._failing_node(
            ModelCallLimitExceededError(
                thread_count=0, run_count=51, thread_limit=None, run_limit=50
            )
        )
        with self.assertLogs(node_module.logger, level="ERROR"):
            with self.assertRaises(DeepAgentLimitError):
                node.invoke([HumanMessage("go")])

    def test_the_recursion_backstop_normalizes_into_the_limit_family(self):
        node = self._failing_node(GraphRecursionError("too deep"))
        with self.assertLogs(node_module.logger, level="ERROR"):
            with self.assertRaises(DeepAgentLimitError):
                node.invoke([HumanMessage("go")])

    def test_anything_else_becomes_a_node_error(self):
        node = self._failing_node(ValueError("provider exploded"))
        with self.assertLogs(node_module.logger, level="ERROR"):
            with self.assertRaises(DeepAgentNodeError):
                node.invoke([HumanMessage("go")])

    def test_a_missing_answer_reports_what_the_model_did_instead(self):
        node = _node(response_format=_StubAnswer)
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [AIMessage(content="I give up")]}
        node._agent = agent
        with self.assertRaises(DeepAgentNodeError) as caught:
            node.invoke([HumanMessage("go")])
        self.assertIn("no tools", str(caught.exception))

    def test_no_answer_schema_means_no_answer_is_expected(self):
        node = _node()
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [AIMessage(content="wrote the records")]}
        node._agent = agent
        self.assertEqual(node.invoke([HumanMessage("go")]).content, "wrote the records")


class TelemetryTests(SimpleTestCase):
    def _result(self) -> dict:
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"file_path": "/skills/deals/SKILL.md"},
                            "id": "c1",
                            "type": "tool_call",
                        }
                    ],
                    usage_metadata={
                        "input_tokens": 900,
                        "output_tokens": 100,
                        "total_tokens": 1000,
                    },
                ),
                AIMessage(content="done"),
            ]
        }

    def test_metrics_reach_the_hook_and_the_attribute(self):
        seen = {}

        class _Recording(_Node):
            def on_run_complete(self, metrics, result):
                seen.update(metrics)

        node = _Recording(llm=MagicMock(), config={})
        agent = MagicMock()
        agent.invoke.return_value = self._result()
        node._agent = agent
        node.invoke([HumanMessage("go")])

        self.assertEqual(seen["skills_used"], ["deals"])
        self.assertEqual(seen["skills_used_count"], 1)
        self.assertEqual(seen["model_calls"], 1)
        self.assertEqual(seen["total_tokens"], 1000)
        self.assertIn("cache_hit_rate", seen)
        self.assertGreaterEqual(seen["elapsed_seconds"], 0)
        self.assertEqual(node.last_metrics, seen)

    def test_extra_trace_metadata_is_merged(self):
        class _Extra(_Node):
            def extra_trace_metadata(self, result):
                return {"record_types": ["deals"]}

        node = _Extra(llm=MagicMock(), config={})
        agent = MagicMock()
        agent.invoke.return_value = self._result()
        node._agent = agent
        node.invoke([HumanMessage("go")])
        self.assertEqual(node.last_metrics["record_types"], ["deals"])

    def test_the_whole_result_state_is_kept_for_the_caller(self):
        node = _node()
        agent = MagicMock()
        result = self._result()
        agent.invoke.return_value = result
        node._agent = agent
        node.invoke([HumanMessage("go")])
        self.assertIs(node.last_result, result)


class SkillWiringTests(SimpleTestCase):
    def test_without_skills_the_browsing_tools_are_withheld(self):
        """An empty virtual filesystem gives ls/glob/grep nothing to find."""
        self.assertIn("ls", _node().get_excluded_tools())

    def test_with_skills_the_browsing_tools_stay(self):
        class _Skilled(_Node):
            skill_names = None

            def get_skill_source(self):
                return _StaticSource(SkillDocument("deals", "deal text"))

        self.assertEqual(list(_Skilled(llm=MagicMock(), config={}).get_excluded_tools()), [])

    def test_skill_names_of_an_empty_iterable_exposes_nothing(self):
        class _Skilled(_Node):
            skill_names = ()

            def get_skill_source(self):
                return _StaticSource(SkillDocument("deals", "deal text"))

        node = _Skilled(llm=MagicMock(), config={})
        self.assertEqual(node._skill_files(), {})
        self.assertIn("ls", node.get_excluded_tools())

    def test_a_missing_skills_root_is_not_an_error(self):
        class _Skilled(_Node):
            skill_names = None

            def get_skill_source(self):
                return FilesystemSkillSource(Path("/nonexistent/skills"))

        self.assertEqual(_Skilled(llm=MagicMock(), config={})._skill_files(), {})


class _StaticSource:
    def __init__(self, *skills):
        self.skills = skills

    def iter_skills(self):
        return self.skills


class ScratchpadScopingTests(SimpleTestCase):
    """``wants_scratchpad`` keeps the write tools an empty filesystem would not justify."""

    def test_a_scratchpad_surface_keeps_the_write_tools(self):
        node = _node(wants_scratchpad=True)
        excluded = set(node.get_excluded_tools())
        self.assertNotIn("write_file", excluded)
        self.assertNotIn("ls", excluded)
        self.assertNotIn("edit_file", excluded)

    def test_a_scratchpad_surface_still_drops_the_search_tools(self):
        """The agent wrote the files, so it knows the paths; glob/grep buy nothing."""
        excluded = set(_node(wants_scratchpad=True).get_excluded_tools())
        self.assertEqual(excluded, {"glob", "grep", "execute"})

    def test_without_the_opt_in_nothing_changes(self):
        self.assertIn("write_file", set(_node().get_excluded_tools()))


class _TwoSchemaNode(_Node):
    """A surface whose second state modifier is its opening user message."""

    state_modifier_schema = [
        BasePromptSchema(description="contract", prompt="THE CONTRACT"),
        BasePromptSchema(description="opening", prompt="READ {DOC}", required_placeholders=["DOC"]),
    ]
    user_prompt_index = 1

    def get_custom_placeholders_data(self):
        return {"DOC": "the document"}


class UserPromptSlotTests(SimpleTestCase):
    """The user-prompt slot: one state modifier that is not system prompt."""

    def _two_schema_node(self, **attrs) -> _TwoSchemaNode:
        node = _TwoSchemaNode(llm=MagicMock(), config={})
        for name, value in attrs.items():
            setattr(node, name, value)
        return node

    def test_the_user_prompt_entry_is_not_in_the_system_prompt(self):
        node = self._two_schema_node()
        self.assertEqual(node.build_system_prompt(), "THE CONTRACT")

    def test_the_user_prompt_is_the_formatted_entry(self):
        self.assertEqual(self._two_schema_node().build_user_prompt(), "READ the document")

    def test_a_negative_index_resolves_the_way_indexing_does(self):
        node = self._two_schema_node(user_prompt_index=-1)
        self.assertEqual(node.build_user_prompt(), "READ the document")
        self.assertEqual(node.build_system_prompt(), "THE CONTRACT")

    def test_no_slot_means_every_entry_is_system_prompt(self):
        node = self._two_schema_node(user_prompt_index=None)
        self.assertEqual(node.build_system_prompt(), "THE CONTRACT\n\nREAD the document")
        self.assertEqual(node.build_user_prompt(), "")

    def test_an_out_of_range_index_degrades_instead_of_raising(self):
        """A misdeclared index must not fail the run with a bare IndexError."""
        node = self._two_schema_node(user_prompt_index=7)
        with self.assertLogs(node_module.logger, level="ERROR"):
            self.assertEqual(node.build_user_prompt(), "")
        self.assertEqual(node.build_system_prompt(), "THE CONTRACT\n\nREAD the document")

    def test_a_conditional_system_entry_is_still_skipped(self):
        class _Conditional(_TwoSchemaNode):
            state_modifier_schema = [
                BasePromptSchema(
                    description="off",
                    prompt="NEVER",
                    conditional_rule=lambda data: False,
                ),
                BasePromptSchema(description="opening", prompt="OPEN"),
            ]

        node = _Conditional(llm=MagicMock(), config={})
        self.assertIsNone(node.build_system_prompt())
        self.assertEqual(node.build_user_prompt(), "OPEN")


class PromptSchemaIsolationTests(SimpleTestCase):
    """Two schemas built with no placeholder data must not share one dict."""

    def test_placeholders_data_is_not_shared_between_schemas(self):
        first = BasePromptSchema(description="a", prompt="a")
        second = BasePromptSchema(description="b", prompt="b")
        first.placeholders_data["DOC"] = "leaked"
        self.assertEqual(second.placeholders_data, {})

    def test_required_placeholders_is_not_shared_between_schemas(self):
        first = BasePromptSchema(description="a", prompt="a")
        second = BasePromptSchema(description="b", prompt="b")
        first.required_placeholders.append("DOC")
        self.assertEqual(second.required_placeholders, [])

    def test_two_nodes_do_not_share_their_class_level_schemas(self):
        """A per-run payload in a prompt must not reach the next run's prompt."""

        class _PerRun(_Node):
            state_modifier_schema = [BasePromptSchema(description="d", prompt="{DOC}")]

            def __init__(self, doc, **kwargs):
                self.doc = doc
                super().__init__(**kwargs)

            def get_custom_placeholders_data(self):
                return {"DOC": self.doc}

        first = _PerRun("first document", llm=MagicMock(), config={})
        second = _PerRun("second document", llm=MagicMock(), config={})
        self.assertEqual(first.build_system_prompt(), "first document")
        self.assertEqual(second.build_system_prompt(), "second document")
        self.assertEqual(
            _PerRun.state_modifier_schema[0].placeholders_data,
            {},
            "the class attribute was mutated by a run",
        )


class NoTracingBackendTests(SimpleTestCase):
    def test_the_package_imports_no_tracing_backend(self):
        """A copy-paste from a LangSmith-based implementation is how this comes back."""
        package = Path(node_module.__file__).parent
        offenders = [
            path.name
            for path in package.rglob("*.py")
            if "tests" not in path.parts and "langsmith" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


class ScriptedRunTests(SimpleTestCase):
    """A real deepagents graph, driven by a scripted model."""

    def _run(self, script, **attrs):
        model = ScriptedChatModel(script)
        node = _node(model=model, **attrs)
        message = node.invoke([HumanMessage("parse this document")])
        return node, model, message

    def test_a_scripted_run_calls_its_tools_and_finishes(self):
        node, model, message = self._run(
            [
                ScriptedTurn(
                    tool_calls=[("search_document", {"query": "annuitant"})],
                    input_tokens=100,
                    output_tokens=10,
                ),
                ScriptedTurn(
                    tool_calls=[("emit_deals", {"count": 2})], input_tokens=120, output_tokens=10
                ),
                ScriptedTurn(text="finished", input_tokens=130, output_tokens=5),
            ]
        )
        called = RecordedCalls.from_messages(node.last_result["messages"]).names
        self.assertEqual(called, ["search_document", "emit_deals"])
        self.assertEqual(message.content, "finished")
        self.assertEqual(node.last_metrics["model_calls"], 3)
        self.assertEqual(node.last_metrics["total_tokens"], 375)
        self.assertEqual(node.last_metrics["skills_used"], [])

    def test_the_surface_tools_are_bound_and_the_browsing_tools_are_not(self):
        _, model, _ = self._run([ScriptedTurn(text="nothing to do")])
        bound = set(model.bound_tool_names[0])
        self.assertIn("search_document", bound)
        self.assertIn("emit_deals", bound)
        self.assertFalse(bound & {"ls", "glob", "grep"})

    def test_the_model_call_cap_aborts_the_run_as_a_limit_error(self):
        script = [ScriptedTurn(tool_calls=[("search_document", {"query": "x"})])]
        with self.assertLogs(node_module.logger, level="ERROR"):
            with self.assertRaises(DeepAgentLimitError):
                self._run(script, limits=DeepAgentLimits(max_model_calls=2, soft_model_calls=99))

    def test_the_soft_cap_withdraws_everything_but_the_finalize_tools(self):
        script = [
            ScriptedTurn(tool_calls=[("search_document", {"query": "x"})]),
            ScriptedTurn(tool_calls=[("emit_deals", {"count": 1})]),
            ScriptedTurn(text="done"),
        ]
        limits = DeepAgentLimits(soft_model_calls=1, finalize_tools=frozenset({"emit_deals"}))
        with self.assertLogs("baseapp_ai_langkit.deep_agents.limits", level="WARNING"):
            _, model, _ = self._run(script, limits=limits)
        # The first call is unconstrained; every later one keeps only the finalize tool.
        self.assertIn("search_document", model.bound_tool_names[0])
        self.assertEqual(model.bound_tool_names[1], ["emit_deals"])

    def test_the_system_prompt_reaches_the_model(self):
        class _Prompted(_Node):
            def build_system_prompt(self):
                return "you are a careful parser"

        model = ScriptedChatModel([ScriptedTurn(text="ok")])
        _Prompted(llm=model, config={}).invoke([HumanMessage("go")])
        # deepagents' own middlewares append their blocks to the system message, so the
        # caller's prompt is the first text block rather than the whole content.
        self.assertIn(
            "you are a careful parser",
            builder.stringify_content(model.received_messages[0][0].content),
        )

    def test_the_recursion_limit_rides_the_invoke_config(self):
        node = _node(limits=DeepAgentLimits(recursion_limit=42))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [AIMessage(content="ok")]}
        node._agent = agent
        node.invoke([HumanMessage("go")])
        self.assertEqual(agent.invoke.call_args.kwargs["config"]["recursion_limit"], 42)

    def test_the_runnable_config_is_passed_through(self):
        callback = MagicMock()
        node = _Node(llm=MagicMock(), config={"callbacks": [callback], "run_name": "named"})
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [AIMessage(content="ok")]}
        node._agent = agent
        node.invoke([HumanMessage("go")])
        config = agent.invoke.call_args.kwargs["config"]
        self.assertEqual(config["callbacks"], [callback])
        self.assertEqual(config["run_name"], "named")


class BuildIntegrationTests(SimpleTestCase):
    def test_the_node_hands_its_own_pieces_to_the_builder(self):
        node = _node(limits=DeepAgentLimits(max_model_calls=3))
        with patch.object(node_module.builder, "build_deep_agent") as build:
            node._get_agent()
        call = build.call_args.kwargs
        self.assertEqual(call["tools"], [search_document, emit_deals])
        self.assertEqual(call["limits"].max_model_calls, 3)
        self.assertFalse(call["has_skills"])
        self.assertIn("ls", call["excluded_tools"])
        self.assertEqual(list(call["extra_middleware"]), [])

    def test_a_surface_can_add_its_own_middleware(self):
        """The hook a surface whose completion rules are its own needs: with no answer
        schema, middleware is the only place a run can be inspected before it ends."""
        extra = AgentMiddleware()

        class _WithMiddleware(_Node):
            def get_extra_middleware(self):
                return [extra]

        node = _WithMiddleware(llm=MagicMock(), config={})
        with patch.object(node_module.builder, "build_deep_agent") as build:
            node._get_agent()

        self.assertEqual(list(build.call_args.kwargs["extra_middleware"]), [extra])
