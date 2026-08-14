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
    DeepAgentModelCallError,
    DeepAgentStructuredOutputError,
    DeepAgentTimeoutError,
    DeepAgentTokenBudgetError,
    HardLimitsMiddleware,
    PlanningLoopMiddleware,
    RunBudget,
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
    """The three shapes a soft breach can take: an answer tool, finalize tools, neither."""

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


class RunBudgetTests(SimpleTestCase):
    """The shared pool, on its own: the arithmetic the tree-wide caps rest on."""

    def test_it_starts_empty(self):
        budget = RunBudget()
        self.assertEqual((budget.model_calls, budget.tokens), (0, 0))

    def test_the_root_is_observed_rather_than_added(self):
        """The root's run is still going, so its counts are a reading, not a contribution."""
        budget = RunBudget()
        budget.observe_root(2, 500)
        budget.observe_root(3, 900)
        self.assertEqual((budget.model_calls, budget.tokens), (3, 900))

    def test_a_stale_root_reading_cannot_lower_the_total(self):
        budget = RunBudget()
        budget.observe_root(5, 1000)
        budget.observe_root(1, 10)
        self.assertEqual((budget.model_calls, budget.tokens), (5, 1000))

    def test_finished_runs_accumulate(self):
        """Thirteen survey windows are thirteen contributions, not one overwriting twelve."""
        budget = RunBudget()
        for _ in range(3):
            budget.close_run(2, 100)
        self.assertEqual((budget.model_calls, budget.tokens), (6, 300))

    def test_the_root_and_the_subagents_share_one_total(self):
        budget = RunBudget()
        budget.close_run(4, 400)
        budget.observe_root(2, 250)
        self.assertEqual((budget.model_calls, budget.tokens), (6, 650))

    def test_a_finished_runs_own_counts_replace_its_live_reading(self):
        """The reading is taken before a call, so it is always a call short at the end."""
        budget = RunBudget()
        budget.close_run(4, 400)
        budget.observe_root(2, 200)
        self.assertEqual(budget.totals_including(3, 350), (7, 750))

    def test_a_lower_reported_count_cannot_shrink_the_total(self):
        budget = RunBudget()
        budget.observe_root(5, 500)
        self.assertEqual(budget.totals_including(1, 10), (5, 500))

    def test_the_deadlines_are_fixed_on_the_first_call(self):
        """Otherwise every delegation restarts the tree's clock."""
        budget = RunBudget()
        first = budget.deadlines(10, 20)
        self.assertEqual(budget.deadlines(1000, 2000), first)

    def test_reset_empties_the_pool_and_the_clock(self):
        budget = RunBudget()
        budget.close_run(4, 400)
        budget.observe_root(2, 200)
        deadlines = budget.deadlines(10, 20)
        budget.reset()
        self.assertEqual((budget.model_calls, budget.tokens), (0, 0))
        self.assertNotEqual(budget.deadlines(10, 20), deadlines)


class TreeWideLimitTests(SimpleTestCase):
    """What the governors count once a budget is in play.

    A subagent's messages never reach the root, so every assertion here is about a number
    the root could not have seen in its own message list.
    """

    def _state(self, messages: Optional[List] = None) -> dict:
        return {
            "deep_agent_deadline": time.monotonic() + 60,
            "deep_agent_soft_deadline": time.monotonic() + 60,
            "messages": messages if messages is not None else [],
        }

    def test_a_subagents_spend_counts_against_the_roots_hard_budget(self):
        budget = RunBudget()
        budget.close_run(1, 900)
        root = _middleware(hard_token_budget=1000, budget=budget)
        with self.assertRaises(DeepAgentTokenBudgetError):
            root.before_model(self._state([_spent(200)]), None)

    def test_without_a_budget_the_same_run_is_within_its_budget(self):
        """The control: local counting is what made the fan-out invisible."""
        self.assertIsNone(
            _middleware(hard_token_budget=1000).before_model(self._state([_spent(200)]), None)
        )

    def test_a_subagents_calls_count_against_the_tree_wide_call_cap(self):
        budget = RunBudget()
        for _ in range(6):
            budget.close_run(2, 10)
        root = _middleware(max_model_calls=12, budget=budget)
        with self.assertRaises(DeepAgentModelCallError):
            root.before_model(self._state(), None)

    def test_without_a_budget_the_call_cap_counts_only_this_run(self):
        """The control for the case above: twelve calls spent elsewhere are invisible."""
        self.assertIsNone(
            _middleware(max_model_calls=12).before_model(self._state([_spent(10)]), None)
        )

    def test_the_root_contributes_its_own_spend_to_the_pool(self):
        budget = RunBudget()
        _middleware(budget=budget).before_model(self._state([_spent(300), _spent(200)]), None)
        self.assertEqual((budget.model_calls, budget.tokens), (2, 500))

    def test_a_subagent_reads_the_pool_plus_its_own_unclosed_spend(self):
        """Its own run has not ended, so nothing has contributed it yet."""
        budget = RunBudget()
        budget.observe_root(1, 700)
        subagent = _middleware(hard_token_budget=1000, budget=budget, is_root=False)
        with self.assertRaises(DeepAgentTokenBudgetError):
            subagent.before_model(self._state([_spent(400)]), None)

    def test_a_subagent_does_not_contribute_until_its_run_ends(self):
        budget = RunBudget()
        subagent = _middleware(budget=budget, is_root=False)
        subagent.before_model(self._state([_spent(300)]), None)
        self.assertEqual(budget.tokens, 0)
        subagent.after_agent(self._state([_spent(300)]), None)
        self.assertEqual((budget.model_calls, budget.tokens), (1, 300))

    def test_the_root_does_not_contribute_on_after_agent(self):
        """Its spend is already counted live; adding it again would double it."""
        budget = RunBudget()
        root = _middleware(budget=budget)
        root.before_model(self._state([_spent(300)]), None)
        root.after_agent(self._state([_spent(300)]), None)
        self.assertEqual((budget.model_calls, budget.tokens), (1, 300))

    def test_after_agent_is_a_no_op_without_a_budget(self):
        self.assertIsNone(_middleware(is_root=False).after_agent(self._state([_spent(10)]), None))

    def test_every_run_in_the_tree_shares_one_deadline(self):
        budget = RunBudget()
        root = _middleware(run_timeout_seconds=600, budget=budget).before_agent({}, None)
        later = _middleware(run_timeout_seconds=600, budget=budget, is_root=False).before_agent(
            {}, None
        )
        self.assertEqual(root, later)

    def test_without_a_budget_each_run_starts_its_own_clock(self):
        first = _middleware(run_timeout_seconds=600).before_agent({}, None)
        second = _middleware(run_timeout_seconds=600).before_agent({}, None)
        self.assertNotEqual(first["deep_agent_deadline"], second["deep_agent_deadline"])

    def test_a_subagents_soft_breach_asks_it_to_finish_without_an_error(self):
        """Nothing to force is the expected shape for a subagent, not a misconfiguration."""
        state = {"deep_agent_soft_deadline": time.monotonic() - 1, "messages": []}
        subagent = _middleware(structured_tool_name=None, is_root=False)
        with self.assertLogs(limits.logger, level="INFO") as logged:
            subagent.wrap_model_call(_request(state), lambda r: _tool_call_response())
        self.assertFalse([line for line in logged.output if line.startswith("ERROR")])


class BuildHardLimitMiddlewareTests(SimpleTestCase):
    def test_the_stack_is_always_three_governors(self):
        stack = build_hard_limit_middleware(STRUCTURED_TOOL)
        self.assertIsInstance(stack[0], ModelCallLimitMiddleware)
        self.assertIsInstance(stack[1], HardLimitsMiddleware)
        self.assertIsInstance(stack[2], PlanningLoopMiddleware)

    def test_the_budget_reaches_the_governor(self):
        budget = RunBudget()
        _, hard, _ = build_hard_limit_middleware(None, budget=budget)
        self.assertIs(hard.budget, budget)
        self.assertTrue(hard.is_root)

    def test_a_subagent_stack_governs_against_the_same_pool(self):
        budget = RunBudget()
        _, hard, _ = build_hard_limit_middleware(None, budget=budget, is_root=False)
        self.assertIs(hard.budget, budget)
        self.assertFalse(hard.is_root)

    def test_a_subagent_stack_carries_no_finalize_tools(self):
        """They name the tools that record the root's work, which a subagent does not hold."""
        profile = DeepAgentLimits(finalize_tools=frozenset({"emit"}))
        _, hard, _ = build_hard_limit_middleware(None, limits=profile, is_root=False)
        self.assertEqual(hard.finalize_tools, frozenset())

    def test_the_tree_wide_call_cap_is_only_set_with_a_budget(self):
        profile = DeepAgentLimits(max_model_calls=9)
        _, without, _ = build_hard_limit_middleware(None, limits=profile)
        _, with_budget, _ = build_hard_limit_middleware(None, limits=profile, budget=RunBudget())
        self.assertIsNone(without.max_model_calls)
        self.assertEqual(with_budget.max_model_calls, 9)

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
