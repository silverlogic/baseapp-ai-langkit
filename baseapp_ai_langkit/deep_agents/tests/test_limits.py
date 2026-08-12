"""Unit tests for the deep agent's hard per-run limits (no DB, no LLM, no graph).

The middleware hooks are exercised directly against hand-built message states: the
shapes mirror what langchain's structured-output retry loop actually puts in state,
including the runaway this module was written to make impossible.
"""

import time
from typing import List, Optional
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from baseapp_ai_langkit.deep_agents import limits
from baseapp_ai_langkit.deep_agents.limits import (
    BUNDLED_ANSWER_NOTICE,
    FINALIZE_ANSWER_NOTICE,
    FINALIZE_BARE_NOTICE,
    FINALIZE_TOOLS_NOTICE,
    PLANNING_LOOP_NOTICE,
    PLANNING_TOOL_NAME,
    DeepAgentLimits,
    DeepAgentStructuredOutputError,
    DeepAgentTimeoutError,
    DeepAgentTokenBudgetError,
    HardLimitsMiddleware,
    PlanningLoopMiddleware,
    build_hard_limit_middleware,
    describe_last_model_turn,
    model_call_count,
    spent_tokens,
)

STRUCTURED_TOOL = "StubAnswer"


def _named_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _middleware(**kwargs) -> HardLimitsMiddleware:
    kwargs.setdefault("structured_tool_name", STRUCTURED_TOOL)
    return HardLimitsMiddleware(**kwargs)


def _request(state: dict, tools: Optional[List] = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=[HumanMessage("question")],
        state=state,
        runtime=None,
        tools=tools if tools is not None else [_named_tool("search"), _named_tool("emit")],
    )


def _spent(total_tokens: int) -> AIMessage:
    """An AI message that spent `total_tokens` on its model call."""
    return AIMessage(
        content="",
        usage_metadata={
            "input_tokens": total_tokens - 10,
            "output_tokens": 10,
            "total_tokens": total_tokens,
        },
    )


def _answer_call(name: str = STRUCTURED_TOOL, stop_reason: str = "tool_use") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {}, "id": "call-1", "type": "tool_call"}],
        response_metadata={"stop_reason": stop_reason},
    )


def _parse_failure() -> ToolMessage:
    """The ToolMessage langchain appends when the structured output fails to parse."""
    return ToolMessage(
        content=(
            f"Error: Failed to parse structured output for tool '{STRUCTURED_TOOL}': "
            "1 validation error. Please fix your mistakes."
        ),
        tool_call_id="call-1",
        name=STRUCTURED_TOOL,
    )


def _tool_call_response() -> ModelResponse:
    return ModelResponse(result=[_answer_call()])


def _bundled_response(structured_response=None) -> ModelResponse:
    """The answer tool called in the same message as an ordinary tool.

    With `structured_response=None` the answer was rejected, the shape that skips
    langchain's retry entirely and kills real runs.
    """
    message = AIMessage(
        content="Submitting.",
        tool_calls=[
            {"name": PLANNING_TOOL_NAME, "args": {}, "id": "t1", "type": "tool_call"},
            {"name": STRUCTURED_TOOL, "args": {}, "id": "a1", "type": "tool_call"},
        ],
    )
    return ModelResponse(result=[message], structured_response=structured_response)


class UsageCounterTests(SimpleTestCase):
    def test_counts_only_real_model_calls(self):
        """Replayed answers re-enter as plain AIMessages and must count zero."""
        messages = [
            HumanMessage("earlier question"),
            AIMessage(content="earlier answer"),
            _spent(1000),
            _spent(2500),
        ]
        self.assertEqual(spent_tokens(messages), 3500)
        self.assertEqual(model_call_count(messages), 2)


class DescribeLastModelTurnTests(SimpleTestCase):
    def test_reports_no_ai_message(self):
        self.assertIn("no AI message", describe_last_model_turn([HumanMessage("q")]))

    def test_reports_the_tools_called_and_the_finish_reason(self):
        described = describe_last_model_turn([_answer_call(stop_reason="max_tokens")])
        self.assertIn(STRUCTURED_TOOL, described)
        self.assertIn("max_tokens", described)


class HardTierTests(SimpleTestCase):
    def test_before_agent_sets_future_deadlines(self):
        update = _middleware(run_timeout_seconds=600).before_agent({}, None)
        self.assertGreater(update["deep_agent_deadline"], time.monotonic())
        self.assertLess(update["deep_agent_soft_deadline"], update["deep_agent_deadline"])

    def test_before_model_passes_within_deadline(self):
        self.assertIsNone(
            _middleware().before_model({"deep_agent_deadline": time.monotonic() + 60}, None)
        )

    def test_before_model_raises_past_deadline(self):
        with self.assertRaises(DeepAgentTimeoutError):
            _middleware().before_model({"deep_agent_deadline": time.monotonic() - 1}, None)

    def test_before_model_tolerates_a_missing_deadline(self):
        """A state restored without the untracked deadline must not crash."""
        self.assertIsNone(_middleware().before_model({}, None))

    def test_before_model_raises_past_the_hard_token_budget(self):
        state = {
            "deep_agent_deadline": time.monotonic() + 60,
            "messages": [_spent(300), _spent(250)],
        }
        with self.assertRaises(DeepAgentTokenBudgetError):
            _middleware(hard_token_budget=500).before_model(state, None)


class SoftTierTests(SimpleTestCase):
    """The three §4.2 shapes: an answer tool, finalize tools, and neither."""

    def _forced(self, middleware: HardLimitsMiddleware, state: dict, **kwargs) -> ModelRequest:
        seen = {}

        def handler(received: ModelRequest) -> ModelResponse:
            seen["request"] = received
            return _tool_call_response()

        with self.assertLogs(limits.logger, level="WARNING"):
            middleware.wrap_model_call(_request(state, **kwargs), handler)
        return seen["request"]

    def test_untouched_below_all_soft_limits(self):
        state = {"deep_agent_soft_deadline": time.monotonic() + 60, "messages": [_spent(1000)]}
        request = _request(state)
        seen = {}

        def handler(received: ModelRequest) -> ModelResponse:
            seen["request"] = received
            return _tool_call_response()

        _middleware().wrap_model_call(request, handler)
        self.assertIs(seen["request"], request)

    def test_soft_token_budget_forces_the_answer(self):
        state = {"deep_agent_soft_deadline": time.monotonic() + 60, "messages": [_spent(600)]}
        forced = self._forced(_middleware(soft_token_budget=500), state)
        # Emptying the list strips the regular tools; langchain re-appends the answer.
        self.assertEqual(forced.tools, [])
        self.assertEqual(
            forced.messages[-1].content, FINALIZE_ANSWER_NOTICE.format(tool_name=STRUCTURED_TOOL)
        )

    def test_soft_deadline_forces_finalization(self):
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        self.assertEqual(self._forced(_middleware(), state).tools, [])

    def test_soft_model_call_count_forces_finalization(self):
        state = {
            "deep_agent_soft_deadline": time.monotonic() + 60,
            "messages": [_spent(100), _spent(100)],
        }
        self.assertEqual(self._forced(_middleware(soft_model_calls=2), state).tools, [])

    def test_finalize_tools_keep_only_those_tools(self):
        """A surface whose result is written by tools must keep the tools that write it."""
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        forced = self._forced(
            _middleware(structured_tool_name=None, finalize_tools=["emit"]), state
        )
        self.assertEqual([tool.name for tool in forced.tools], ["emit"])
        self.assertEqual(
            forced.messages[-1].content, FINALIZE_TOOLS_NOTICE.format(tool_names="emit")
        )

    def test_finalize_tools_that_match_nothing_leave_the_tools_alone(self):
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        forced = self._forced(
            _middleware(structured_tool_name=None, finalize_tools=["nope"]), state
        )
        self.assertEqual([tool.name for tool in forced.tools], ["search", "emit"])
        self.assertEqual(forced.messages[-1].content, FINALIZE_BARE_NOTICE)

    def test_neither_answer_nor_finalize_tools_degrades_to_a_request(self):
        """Nothing can be forced, so the tools stay and the notice is only a request."""
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        forced = self._forced(_middleware(structured_tool_name=None), state)
        self.assertEqual([tool.name for tool in forced.tools], ["search", "emit"])
        self.assertEqual(forced.messages[-1].content, FINALIZE_BARE_NOTICE)

    def test_the_notice_never_enters_conversation_state(self):
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        request = _request(state)
        with self.assertLogs(limits.logger, level="WARNING"):
            _middleware().wrap_model_call(request, lambda r: _tool_call_response())
        self.assertEqual(len(request.messages), 1)


class BundledAnswerRetryTests(SimpleTestCase):
    def _state(self) -> dict:
        return {"deep_agent_soft_deadline": time.monotonic() + 60, "messages": []}

    def test_a_rejected_bundled_answer_is_re_asked(self):
        responses = [_bundled_response(), _bundled_response(structured_response={"text": "ok"})]
        seen = []

        def handler(request: ModelRequest) -> ModelResponse:
            seen.append(request)
            return responses[len(seen) - 1]

        with self.assertLogs(limits.logger, level="WARNING"):
            _middleware().wrap_model_call(_request(self._state()), handler)
        self.assertEqual(len(seen), 2)
        self.assertEqual(
            seen[1].messages[-1].content, BUNDLED_ANSWER_NOTICE.format(tool_name=STRUCTURED_TOOL)
        )

    def test_retries_are_bounded(self):
        seen = []

        def handler(request: ModelRequest) -> ModelResponse:
            seen.append(request)
            return _bundled_response()

        with self.assertLogs(limits.logger, level="WARNING"):
            _middleware(max_bundled_answer_retries=2).wrap_model_call(
                _request(self._state()), handler
            )
        self.assertEqual(len(seen), 3)  # the first call plus two retries

    def test_a_lone_rejected_answer_is_left_to_langchain(self):
        """langchain already retries this shape; re-asking here would multiply attempts."""
        seen = []

        def handler(request: ModelRequest) -> ModelResponse:
            seen.append(request)
            return ModelResponse(result=[_answer_call()], structured_response=None)

        _middleware().wrap_model_call(_request(self._state()), handler)
        self.assertEqual(len(seen), 1)

    def test_no_structured_tool_means_no_bundled_repair(self):
        seen = []

        def handler(request: ModelRequest) -> ModelResponse:
            seen.append(request)
            return _bundled_response()

        _middleware(structured_tool_name=None).wrap_model_call(_request(self._state()), handler)
        self.assertEqual(len(seen), 1)


class StructuredOutputAbortTests(SimpleTestCase):
    def test_a_truncated_answer_fails_immediately(self):
        """Retrying cannot fix a too-small output cap, so it is pure waste."""
        with self.assertRaises(DeepAgentStructuredOutputError):
            _middleware().after_model({"messages": [_answer_call(stop_reason="max_tokens")]}, None)

    def test_a_truncated_call_to_another_tool_is_not_our_problem(self):
        _middleware().after_model(
            {"messages": [_answer_call(name="search", stop_reason="max_tokens")]}, None
        )

    def test_a_streak_of_parse_failures_aborts_with_the_rejections(self):
        messages = [_answer_call(), _parse_failure(), _answer_call(), _parse_failure()]
        with self.assertRaises(DeepAgentStructuredOutputError) as caught:
            _middleware(max_consecutive_failures=2).after_model({"messages": messages}, None)
        self.assertIn("validation error", str(caught.exception))

    def test_a_single_failure_is_tolerated(self):
        _middleware(max_consecutive_failures=2).after_model(
            {"messages": [_answer_call(), _parse_failure()]}, None
        )

    def test_a_real_tool_result_resets_the_streak(self):
        messages = [
            _answer_call(),
            _parse_failure(),
            ToolMessage(content="found it", tool_call_id="s1", name="search"),
            _answer_call(),
            _parse_failure(),
        ]
        _middleware(max_consecutive_failures=2).after_model({"messages": messages}, None)

    def test_the_rejected_payload_rides_the_error(self):
        rejected = AIMessage(
            content="",
            tool_calls=[
                {"name": STRUCTURED_TOOL, "args": {"text": 1}, "id": "call-1", "type": "tool_call"}
            ],
        )
        with self.assertRaises(DeepAgentStructuredOutputError) as caught:
            _middleware(max_consecutive_failures=1).after_model(
                {"messages": [rejected, _parse_failure()]}, None
            )
        self.assertEqual(caught.exception.rejected_payload, {"text": 1})

    def test_the_checks_are_skipped_without_a_structured_tool(self):
        _middleware(structured_tool_name=None).after_model(
            {"messages": [_answer_call(stop_reason="max_tokens")]}, None
        )


class PlanningLoopTests(SimpleTestCase):
    def _planning_call(self, name: str = PLANNING_TOOL_NAME) -> ToolMessage:
        return ToolMessage(content="ok", tool_call_id="p1", name=name)

    def _run(self, messages: list) -> ModelRequest:
        seen = {}

        def handler(request: ModelRequest) -> ModelResponse:
            seen["request"] = request
            return _tool_call_response()

        request = ModelRequest(
            model=MagicMock(),
            messages=[HumanMessage("q")],
            state={"messages": messages},
            runtime=None,
            tools=[_named_tool(PLANNING_TOOL_NAME), _named_tool("search")],
        )
        PlanningLoopMiddleware(max_consecutive_planning_calls=2).wrap_model_call(request, handler)
        return seen["request"]

    def test_below_the_streak_the_planning_tool_stays(self):
        request = self._run([self._planning_call()])
        self.assertIn(PLANNING_TOOL_NAME, [tool.name for tool in request.tools])

    def test_at_the_streak_the_planning_tool_is_withdrawn(self):
        with self.assertLogs(limits.logger, level="WARNING"):
            request = self._run([self._planning_call(), self._planning_call()])
        self.assertEqual([tool.name for tool in request.tools], ["search"])
        self.assertEqual(
            request.messages[-1].content,
            PLANNING_LOOP_NOTICE.format(tool_name=PLANNING_TOOL_NAME, count=2),
        )

    def test_any_other_tool_call_resets_the_streak(self):
        messages = [
            self._planning_call(),
            self._planning_call(),
            self._planning_call("search"),
        ]
        request = self._run(messages)
        self.assertIn(PLANNING_TOOL_NAME, [tool.name for tool in request.tools])


class BuildHardLimitMiddlewareTests(SimpleTestCase):
    def test_the_stack_is_always_three_governors(self):
        stack = build_hard_limit_middleware(STRUCTURED_TOOL)
        self.assertIsInstance(stack[0], ModelCallLimitMiddleware)
        self.assertIsInstance(stack[1], HardLimitsMiddleware)
        self.assertIsInstance(stack[2], PlanningLoopMiddleware)

    def test_the_profile_sizes_every_governor(self):
        profile = DeepAgentLimits(
            max_model_calls=9,
            soft_timeout_seconds=1,
            timeout_seconds=2,
            soft_token_budget=3,
            hard_token_budget=4,
            soft_model_calls=5,
            max_consecutive_structured_output_failures=6,
            max_consecutive_planning_calls=7,
            finalize_tools=frozenset({"emit"}),
        )
        _, hard, planning = build_hard_limit_middleware(STRUCTURED_TOOL, limits=profile)
        self.assertEqual(hard.soft_run_timeout_seconds, 1)
        self.assertEqual(hard.run_timeout_seconds, 2)
        self.assertEqual(hard.soft_token_budget, 3)
        self.assertEqual(hard.hard_token_budget, 4)
        self.assertEqual(hard.soft_model_calls, 5)
        self.assertEqual(hard.max_consecutive_failures, 6)
        self.assertEqual(hard.finalize_tools, frozenset({"emit"}))
        self.assertEqual(planning.max_consecutive_planning_calls, 7)
