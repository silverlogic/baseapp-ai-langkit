"""Soft and hard runtime limits for one deep-agent run.

Why this exists: langchain's ``create_agent`` compiles the deep-agent graph with
``recursion_limit=10_000`` and retries structured-output parse failures forever
(``ToolStrategy(handle_errors=True)`` appends an error ToolMessage and loops back to
the model with no cap). A single production run once looped 415 model calls over 37
minutes and burned ~52M prompt tokens because the model kept emitting an answer tool
call whose JSON args were truncated by ``max_tokens`` and then degenerated into empty
``{}`` calls. Everything in this module exists to make that outcome impossible.

Two tiers per resource (wall clock, cumulative tokens, model calls):

- **Soft limit**: the run is still allowed to finish, but every model call from then
  on is *forced to finalize*. Which tools survive that depends on how the surface
  produces its result (see :class:`HardLimitsMiddleware`), and a notice is injected
  telling the model to finish with what it already has. The caller gets a best-effort
  result instead of an error.
- **Hard limit**: the run raises a :class:`DeepAgentLimitError` subclass and fails
  loudly. Reached only if finalization itself keeps failing past the soft tier.

Token budgets count *cumulative* ``total_tokens`` across the run's model calls (the
number a tracing backend shows on the run). Every call re-reads the full context
(mostly cache hits), so a healthy complex run accumulates ~0.5-2M and the runaway hit
52M. Tune the budgets with that scale in mind, not per-call sizes.

**The counters cover the whole subagent tree, not one message list.** A subagent is a
separate graph run: its messages never enter the parent's list, and what comes back is a
single ToolMessage holding its final text. Counting the local messages therefore misses
every model call and every token a fan-out spends, which is not a slightly generous
budget but a budget that reports success while measuring nothing. :class:`RunBudget` is
the shared pool that fixes it, and :func:`build_hard_limit_middleware` is what hands the
same pool to a root run and to each of its subagents.

The values are deliberately module constants surfaced through a frozen
:class:`DeepAgentLimits` profile, not admin config: they are safety rails against
runaway spend, and a bad admin edit must not be able to remove them.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import (
    Annotated,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
)

from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
)
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from baseapp_ai_langkit.deep_agents.tool_scoping import tool_name

logger = logging.getLogger(__name__)

# --- Model calls --------------------------------------------------------------
# A healthy run uses ~10-30 calls (tool selection, file reads, the final result);
# the pathological run used 415. Past the soft cap the agent is forced to finalize;
# past the hard cap ModelCallLimitMiddleware raises.
SOFT_MODEL_CALLS_PER_RUN = 35
MAX_MODEL_CALLS_PER_RUN = 50

# --- Wall clock ----------------------------------------------------------------
# Checked around every model call, so a run can overshoot by at most one model-call
# latency (bounded itself by the per-request timeout of the chat model).
SOFT_RUN_TIMEOUT_SECONDS = 240
RUN_TIMEOUT_SECONDS = 360

# --- Token budget ---------------------------------------------------------------
# Cumulative total_tokens (input + output, cache reads included) across the run's
# model calls. See the module docstring for the scale rationale.
SOFT_TOKEN_BUDGET = 400_000
HARD_TOKEN_BUDGET = 600_000

# LangGraph recursion (super-step) backstop for one run, passed at invoke time to
# override the compiled-in 10_000 default. A model cycle costs ~2-3 super-steps
# (model node + middleware hook nodes + tool node), so this sits comfortably above
# MAX_MODEL_CALLS_PER_RUN while still bounding anything that slips past it.
RECURSION_LIMIT = 150

# Consecutive structured-output parse failures tolerated before the run is aborted.
# One-off malformed output deserves a retry; a streak means the model is stuck (e.g.
# truncated or empty tool args) and retrying only burns tokens.
MAX_CONSECUTIVE_STRUCTURED_OUTPUT_FAILURES = 3

# --- Planning loop ---------------------------------------------------------------
# deepagents' planning tool. Writing the plan costs a model call and produces no
# information, so back-to-back writes with no work in between are pure burn.
PLANNING_TOOL_NAME = "write_todos"

# Consecutive planning writes tolerated before the planning tool is withdrawn for one
# call. Re-planning immediately after planning cannot be progress: the model has
# learned nothing between the two, so the second write is at best a re-wording.
MAX_CONSECUTIVE_PLANNING_CALLS = 2

PLANNING_LOOP_NOTICE = (
    "[System notice] You have called {tool_name} {count} times in a row without "
    "doing anything in between, so it has been withdrawn for this step. Re-writing "
    "the plan is not progress. Take the next action your plan already names by "
    "calling one of the remaining tools, and never mark a step complete unless you "
    "actually ran the tool it describes."
)

# Prefix of the ToolMessage langchain emits for a failed structured-output parse
# (STRUCTURED_OUTPUT_ERROR_TEMPLATE in langchain.agents.factory).
_STRUCTURED_OUTPUT_ERROR_PREFIX = "Error:"

# Retries for an answer that was rejected while bundled with other tool calls (see
# `_answer_rejected_while_bundled`). Deliberately NOT part of `DeepAgentLimits`: it is
# not a spend guardrail like the others but a repair for a langchain routing gap, and
# the right number is the same on every surface.
MAX_BUNDLED_ANSWER_RETRIES = 2

BUNDLED_ANSWER_NOTICE = (
    "[System notice] Your {tool_name} call was rejected, and because you bundled it "
    "with other tool calls in the same message the usual retry did not happen. Fix "
    "the problems named in the tool result above, then call {tool_name} again as the "
    "ONLY tool call in that message."
)

#: Forced-finalization notice for a surface whose result is one structured answer.
FINALIZE_ANSWER_NOTICE = (
    "[System notice] This run has reached its resource budget. Stop gathering "
    "information now, your tools have been withdrawn. Using ONLY what you have "
    "already learned above, produce your final answer by calling {tool_name}. If the "
    "analysis is incomplete, say so in the answer and state what could not be checked."
)

#: Forced-finalization notice for a surface whose result is written by tools.
FINALIZE_TOOLS_NOTICE = (
    "[System notice] This run has reached its resource budget. Stop gathering "
    "information now, every other tool has been withdrawn. Using ONLY what you have "
    "already learned above, finish by calling: {tool_names}. Record what you have "
    "rather than nothing, and state anything you could not check."
)

#: Forced-finalization notice for a surface that declared no way to finish. The tools
#: are left in place because withdrawing them would leave the model unable to act at
#: all; this is a degraded configuration and the middleware says so in the log.
FINALIZE_BARE_NOTICE = (
    "[System notice] This run has reached its resource budget. Stop gathering "
    "information now and finish with what you have already learned above."
)


@dataclass(frozen=True)
class DeepAgentLimits:
    """Every per-run resource boundary, as one named profile.

    The middleware stack itself is non-negotiable (every deep-agent build gets the
    same governors), but the numeric boundaries depend on the surface: an interactive
    turn must answer while a user waits, whereas a background job can afford a much
    longer, more expensive run. Values default to the module constants.

    ``finalize_tools`` names the tools that stay bound past the soft threshold. Leave
    it empty for a surface whose result is a structured answer (langchain binds that
    tool outside the request's tool list, so emptying the list is what forces the
    answer). Fill it for a surface whose result is written by tools, otherwise a soft
    breach would strip the only tools that can record the work.
    """

    soft_model_calls: int = SOFT_MODEL_CALLS_PER_RUN
    max_model_calls: int = MAX_MODEL_CALLS_PER_RUN
    soft_timeout_seconds: float = SOFT_RUN_TIMEOUT_SECONDS
    timeout_seconds: float = RUN_TIMEOUT_SECONDS
    soft_token_budget: int = SOFT_TOKEN_BUDGET
    hard_token_budget: int = HARD_TOKEN_BUDGET
    recursion_limit: int = RECURSION_LIMIT
    max_consecutive_structured_output_failures: int = MAX_CONSECUTIVE_STRUCTURED_OUTPUT_FAILURES
    max_consecutive_planning_calls: int = MAX_CONSECUTIVE_PLANNING_CALLS
    finalize_tools: FrozenSet[str] = field(default_factory=frozenset)


DEFAULT_LIMITS = DeepAgentLimits()


class RunBudget:
    """The resource pool one root run shares with every subagent it spawns.

    Exists because the governors cannot count what they cannot see. Each middleware hook
    receives the message list of *its own* graph run, and a subagent's messages never
    reach the parent, so a fan-out that spends thirteen runs' worth of calls and tokens
    is invisible to a parent counting its own messages. One of these, handed to the root
    and to each subagent's governors, is what makes the caps mean "this job" rather than
    "this message list".

    Two slots rather than one running total, because the two kinds of contribution have
    different shapes. The root's spend is *live*: its run is still going, its local count
    only grows, so it is re-observed on every hook and the highest reading wins.  A
    subagent's spend is *closed*: it is added once, when the subagent's run ends, which
    needs no per-invocation bookkeeping and cannot double count however many times the
    same subagent spec is invoked.

    Concurrency: with deepagents' blocking ``task`` tool only one run is ever in flight,
    so the totals are exact. Under ``AsyncSubAgentMiddleware`` two subagents in flight do
    not see each other's unclosed spend, which under-counts until they finish. That is a
    known and deliberate looseness: the alternative is a lock around a counter read on
    every model call, to sharpen a rail whose job is to stop a runaway rather than to bill.
    """

    def __init__(self) -> None:
        self._closed_calls = 0
        self._closed_tokens = 0
        self._root_calls = 0
        self._root_tokens = 0
        self._soft_deadline: Optional[float] = None
        self._deadline: Optional[float] = None

    @property
    def model_calls(self) -> int:
        """Model calls across the tree: the root's live count plus every finished run's."""
        return self._closed_calls + self._root_calls

    @property
    def tokens(self) -> int:
        """Cumulative tokens across the tree, on the same basis as :attr:`model_calls`."""
        return self._closed_tokens + self._root_tokens

    def observe_root(self, calls: int, tokens: int) -> None:
        """Record the root run's counts so far. Monotonic, so re-observing is harmless."""
        self._root_calls = max(self._root_calls, calls)
        self._root_tokens = max(self._root_tokens, tokens)

    def close_run(self, calls: int, tokens: int) -> None:
        """Add a finished subagent run's totals to the pool, once."""
        self._closed_calls += calls
        self._closed_tokens += tokens

    def deadlines(self, soft_seconds: float, hard_seconds: float) -> Tuple[float, float]:
        """The tree's wall-clock deadlines, fixed on the first call.

        Fixed once is the whole point: a subagent's ``before_agent`` fires with a fresh
        clock, so a per-run deadline restarts the timeout every time the root delegates.
        """
        if self._deadline is None:
            now = time.monotonic()
            self._soft_deadline = now + soft_seconds
            self._deadline = now + hard_seconds
        return self._soft_deadline, self._deadline

    def reset(self) -> None:
        """Empty the pool for a fresh run, deadlines included.

        A node caches its compiled agent, so a second ``invoke`` on the same node reuses
        the same middleware and therefore the same budget. Without this the second run
        would start already spent, which would turn "per run" into "per node".
        """
        self._closed_calls = 0
        self._closed_tokens = 0
        self._root_calls = 0
        self._root_tokens = 0
        self._soft_deadline = None
        self._deadline = None


class DeepAgentLimitError(Exception):
    """A hard limit on the deep-agent run was exceeded."""


class DeepAgentTimeoutError(DeepAgentLimitError):
    """The run exceeded its wall-clock budget."""


class DeepAgentModelCallError(DeepAgentLimitError):
    """The tree exceeded its cumulative model-call budget.

    Distinct from langchain's ``ModelCallLimitExceededError``, which counts one run: this
    is the cap that a fan-out can breach without any single run reaching its own limit.
    """


class DeepAgentTokenBudgetError(DeepAgentLimitError):
    """The run exceeded its cumulative token budget."""


class DeepAgentStructuredOutputError(DeepAgentLimitError):
    """The run cannot produce a parseable structured answer.

    ``rejected_payload`` carries the arguments of the last structured answer the parser
    refused, when the model produced one. A caller that can degrade gets the chance to
    keep that work instead of throwing away a whole run over the one rule the model
    could not satisfy. ``None`` when there was never a parseable set of arguments to
    keep, e.g. the max_tokens truncation case.
    """

    def __init__(self, *args, rejected_payload: Optional[dict] = None) -> None:
        super().__init__(*args)
        self.rejected_payload = rejected_payload


class HardLimitsState(AgentState):
    """Agent state extension carrying the run's deadlines.

    ``UntrackedValue`` keeps them out of checkpoint diffs and ``PrivateStateAttr``
    keeps them out of the agent's input/output schema: they exist only while the run
    is in flight.
    """

    deep_agent_soft_deadline: NotRequired[Annotated[float, UntrackedValue, PrivateStateAttr]]
    deep_agent_deadline: NotRequired[Annotated[float, UntrackedValue, PrivateStateAttr]]


def _answer_rejected_while_bundled(response: ModelResponse, structured_tool_name: str) -> bool:
    """Whether a rejected answer was emitted alongside other tool calls.

    The model may call the answer tool in the same message as an ordinary tool, which
    is efficient and works fine when the content is valid. When it is *not* valid,
    langchain's retry loop is defeated: routing sees the sibling call still pending,
    leaves the loop, and the run ends after that single attempt with no structured
    response, no retry, and no error.

    Narrow on purpose. A rejected answer with no siblings is already retried by
    langchain and bounded by ``_check_failure_streak``; re-asking here too would just
    multiply the attempts.
    """
    if response.structured_response is not None:
        return False
    return any(
        structured_tool_name in [call.get("name") for call in message.tool_calls]
        and len(message.tool_calls) > 1
        for message in response.result
        if isinstance(message, AIMessage) and message.tool_calls
    )


def describe_last_model_turn(messages: List[AnyMessage]) -> str:
    """What the model actually did last, for a "no result" failure message.

    Without this the failure reads only as "produced no result", which does not say
    whether the model called the wrong tool, called none at all, or was cut off, and
    that is the difference between a provider fault and a bug in the surface.
    """
    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last_ai is None:
        return "the run contains no AI message at all"
    called = [call.get("name") for call in (last_ai.tool_calls or [])]
    invalid = [call.get("name") for call in (last_ai.invalid_tool_calls or [])]
    finish = (last_ai.response_metadata or {}).get("stop_reason") or (
        last_ai.response_metadata or {}
    ).get("finish_reason")
    text = " ".join(str(last_ai.text or "").split())[:200]
    return (
        f"last AI message called {called or 'no tools'}"
        f"{f', invalid tool calls {invalid}' if invalid else ''}"
        f"{f', finish_reason={finish!r}' if finish else ''}"
        f"{f', text={text!r}' if text else ', no text content'}"
    )


def spent_tokens(messages: List[AnyMessage]) -> int:
    """Cumulative total_tokens across the run's real model calls.

    Only AI messages that came from an actual model call carry ``usage_metadata``;
    messages replayed into the conversation count zero.
    """
    return sum(
        (message.usage_metadata or {}).get("total_tokens", 0)
        for message in messages
        if isinstance(message, AIMessage)
    )


def model_call_count(messages: List[AnyMessage]) -> int:
    """Number of real model calls recorded in the run's messages (see spent_tokens)."""
    return sum(
        1 for message in messages if isinstance(message, AIMessage) and message.usage_metadata
    )


class HardLimitsMiddleware(AgentMiddleware):
    """Force finalization at the soft limits; abort the run at the hard ones.

    Soft tier (``wrap_model_call``): once elapsed time, cumulative tokens, or
    model-call count crosses its soft threshold, every subsequent model request is
    rewritten to finalize. Which tools survive depends on how the surface produces its
    result:

    - ``structured_tool_name`` set and no ``finalize_tools``: the tool list is emptied.
      langchain appends the answer tool *outside* ``request.tools`` and forces
      ``tool_choice="any"`` whenever a response_format is set, so emptying the list
      strips the regular tools and leaves the answer tool, which the model must call.
    - ``finalize_tools`` set: only those tools are kept (plus the answer tool, if any).
      This is the shape for a surface whose result is written by tools rather than
      returned as one object: emptying the list there would strip the only tools that
      can record the work.
    - Neither: the notice is appended and the tools are left alone, with a warning.
      Nothing can be forced, so the soft tier degrades to a request.

    Hard tier, all raising a :class:`DeepAgentLimitError` subclass:

    - ``before_model``: wall-clock deadline (set in ``before_agent``) or cumulative
      token budget exceeded.
    - ``after_model``: the structured-answer tool call was cut off by ``max_tokens``.
      Retrying cannot fix a too-small output cap, so fail immediately.
    - ``after_model``: N consecutive structured-output parse failures. The model is
      stuck in the retry loop; stop feeding it.

    The two ``after_model`` checks and the bundled-answer repair only apply to a
    surface with a structured answer, and are skipped when ``structured_tool_name`` is
    ``None``.
    """

    state_schema: Type[HardLimitsState] = HardLimitsState

    def __init__(
        self,
        *,
        structured_tool_name: Optional[str] = None,
        soft_run_timeout_seconds: float = SOFT_RUN_TIMEOUT_SECONDS,
        run_timeout_seconds: float = RUN_TIMEOUT_SECONDS,
        soft_token_budget: int = SOFT_TOKEN_BUDGET,
        hard_token_budget: int = HARD_TOKEN_BUDGET,
        soft_model_calls: int = SOFT_MODEL_CALLS_PER_RUN,
        max_consecutive_failures: int = MAX_CONSECUTIVE_STRUCTURED_OUTPUT_FAILURES,
        max_bundled_answer_retries: int = MAX_BUNDLED_ANSWER_RETRIES,
        finalize_tools: Iterable[str] = (),
    ) -> None:
        super().__init__()
        self.structured_tool_name = structured_tool_name
        self.soft_run_timeout_seconds = soft_run_timeout_seconds
        self.run_timeout_seconds = run_timeout_seconds
        self.soft_token_budget = soft_token_budget
        self.hard_token_budget = hard_token_budget
        self.soft_model_calls = soft_model_calls
        self.max_consecutive_failures = max_consecutive_failures
        self.max_bundled_answer_retries = max_bundled_answer_retries
        self.finalize_tools = frozenset(finalize_tools)

    def before_agent(self, state: HardLimitsState, runtime: Runtime) -> Dict[str, float]:
        now = time.monotonic()
        return {
            "deep_agent_soft_deadline": now + self.soft_run_timeout_seconds,
            "deep_agent_deadline": now + self.run_timeout_seconds,
        }

    def before_model(self, state: HardLimitsState, runtime: Runtime) -> None:
        deadline = state.get("deep_agent_deadline")
        if deadline is not None and time.monotonic() > deadline:
            raise DeepAgentTimeoutError(
                f"Deep-agent run exceeded its {self.run_timeout_seconds:.0f}s hard "
                "wall-clock budget; aborting before the next model call."
            )
        spent = spent_tokens(state.get("messages", []) or [])
        if spent >= self.hard_token_budget:
            raise DeepAgentTokenBudgetError(
                f"Deep-agent run spent {spent} cumulative tokens, past the hard budget "
                f"of {self.hard_token_budget}; aborting before the next model call."
            )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        reason = self._soft_breach_reason(request.state)
        if reason is None:
            return self._call_retrying_a_bundled_rejection(request, handler)
        notice, tools = self._finalize(request)
        logger.warning(
            "Deep-agent run passed a soft limit (%s); forcing the model to finalize "
            "with the data gathered so far (%s tools left bound).",
            reason,
            len(tools),
        )
        # The notice rides the request only, it never enters conversation state.
        return self._call_retrying_a_bundled_rejection(
            request.override(
                messages=[*request.messages, HumanMessage(content=notice)], tools=tools
            ),
            handler,
        )

    def _finalize(self, request: ModelRequest) -> tuple:
        """The notice and the surviving tool list for a soft-breached request."""
        if self.finalize_tools:
            kept = [tool for tool in request.tools if tool_name(tool) in self.finalize_tools]
            names = sorted(filter(None, (tool_name(tool) for tool in kept)))
            if names:
                return FINALIZE_TOOLS_NOTICE.format(tool_names=", ".join(names)), kept
            logger.error(
                "Deep-agent finalize_tools %s matched none of the bound tools; the soft "
                "limit cannot force this run to finish.",
                sorted(self.finalize_tools),
            )
            return FINALIZE_BARE_NOTICE, list(request.tools)
        if self.structured_tool_name:
            # langchain appends the answer tool outside `request.tools`, so emptying the
            # list strips the regular tools and leaves the model with only the answer.
            return FINALIZE_ANSWER_NOTICE.format(tool_name=self.structured_tool_name), []
        logger.error(
            "Deep-agent run passed a soft limit with neither a structured answer tool "
            "nor finalize_tools declared; nothing can be forced, so the tools are left "
            "in place and the notice is only a request."
        )
        return FINALIZE_BARE_NOTICE, list(request.tools)

    def _call_retrying_a_bundled_rejection(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Give the model back the retries it loses by bundling its answer.

        See ``_answer_rejected_while_bundled`` for the failure this repairs: an answer
        that fails validation while sharing a message with another tool call ends the
        run immediately instead of being retried, so a run that did all of its work
        dies as "produced no final answer".

        Exhausting the retries falls through to the caller, which reports what the
        model did instead.
        """
        response = handler(request)
        if not self.structured_tool_name:
            return response
        for attempt in range(1, self.max_bundled_answer_retries + 1):
            if not _answer_rejected_while_bundled(response, self.structured_tool_name):
                return response
            logger.warning(
                "Deep-agent %s call was rejected while bundled with other tool calls, "
                "which skips langchain's retry (attempt %s of %s). Re-asking for the "
                "answer on its own.",
                self.structured_tool_name,
                attempt,
                self.max_bundled_answer_retries,
            )
            notice = HumanMessage(
                content=BUNDLED_ANSWER_NOTICE.format(tool_name=self.structured_tool_name)
            )
            response = handler(request.override(messages=[*request.messages, notice]))
        return response

    def _soft_breach_reason(self, state: HardLimitsState) -> Optional[str]:
        """Which soft limit (if any) the run has crossed, for the log line."""
        soft_deadline = state.get("deep_agent_soft_deadline")
        if soft_deadline is not None and time.monotonic() > soft_deadline:
            return f"elapsed time > {self.soft_run_timeout_seconds:.0f}s"
        messages = state.get("messages", []) or []
        spent = spent_tokens(messages)
        if spent >= self.soft_token_budget:
            return f"{spent} tokens >= {self.soft_token_budget}"
        calls = model_call_count(messages)
        if calls >= self.soft_model_calls:
            return f"{calls} model calls >= {self.soft_model_calls}"
        return None

    def after_model(self, state: HardLimitsState, runtime: Runtime) -> None:
        if not self.structured_tool_name:
            return
        messages: List[AnyMessage] = state.get("messages", []) or []
        self._check_truncated_structured_answer(messages)
        self._check_failure_streak(messages)

    def _check_truncated_structured_answer(self, messages: List[AnyMessage]) -> None:
        """Fail fast when max_tokens cut off the structured-answer tool call.

        A truncated answer JSON can never parse, and the retry loop re-runs the model
        under the same output cap, so retrying is pure waste (this exact shape caused
        the 415-call runaway).
        """
        last_ai = self._last_ai_message(messages)
        if last_ai is None:
            return
        if (last_ai.response_metadata or {}).get("stop_reason") != "max_tokens":
            return
        called = {call.get("name") for call in (last_ai.tool_calls or [])}
        called |= {call.get("name") for call in (last_ai.invalid_tool_calls or [])}
        if self.structured_tool_name in called:
            raise DeepAgentStructuredOutputError(
                f"The model hit max_tokens while emitting the {self.structured_tool_name} "
                "structured answer, so its JSON can never parse. Raise the model's "
                "`max_tokens` (or shorten the answer format)."
            )

    def _check_failure_streak(self, messages: List[AnyMessage]) -> None:
        """Abort after N consecutive structured-output parse failures."""
        streak = 0
        failures: List[str] = []
        for message in reversed(messages):
            if isinstance(message, ToolMessage) and self._is_parse_failure(message):
                streak += 1
                failures.append(str(message.content))
                if streak >= self.max_consecutive_failures:
                    # The failures themselves go in the message: without them the only
                    # way to learn WHICH rule the model could not satisfy is to dig the
                    # tool messages out of the trace.
                    detail = "\n\n".join(
                        f"Attempt {len(failures) - index}: {text}"
                        for index, text in enumerate(failures)
                    )
                    raise DeepAgentStructuredOutputError(
                        f"The model failed to produce a parseable {self.structured_tool_name} "
                        f"{streak} times in a row; aborting the run instead of retrying. "
                        f"The rejections were:\n\n{detail}",
                        rejected_payload=self._rejected_payload(messages),
                    )
            elif isinstance(message, AIMessage):
                continue  # the retry loop interleaves AI messages with error ToolMessages
            else:
                break

    def _is_parse_failure(self, message: ToolMessage) -> bool:
        return message.name == self.structured_tool_name and str(message.content).startswith(
            _STRUCTURED_OUTPUT_ERROR_PREFIX
        )

    def _rejected_payload(self, messages: List[AnyMessage]) -> Optional[dict]:
        """The arguments of the most recent structured answer the parser refused.

        Matched by ``tool_call_id`` rather than by position: the retry loop interleaves
        AI messages and error ToolMessages, so "the AI message before this one" is not
        reliably the call that produced it. Returns ``None`` when the arguments never
        arrived as a mapping, which is the only shape a caller could do anything with.
        """
        call_id = next(
            (
                message.tool_call_id
                for message in reversed(messages)
                if isinstance(message, ToolMessage) and self._is_parse_failure(message)
            ),
            None,
        )
        if call_id is None:
            return None
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            for call in message.tool_calls or []:
                if call.get("id") == call_id and isinstance(call.get("args"), dict):
                    return call["args"]
        return None

    @staticmethod
    def _last_ai_message(messages: List[AnyMessage]) -> Optional[AIMessage]:
        return next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)


def _trailing_planning_calls(messages: List[AnyMessage]) -> int:
    """How many planning writes end the transcript with no other tool call after them.

    Counts back over ToolMessages only, stopping at the first one from any other tool:
    a single real action resets the streak, which is what makes this a no-progress
    detector rather than a per-run quota on planning.
    """
    streak = 0
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", None) != PLANNING_TOOL_NAME:
            break
        streak += 1
    return streak


class PlanningLoopMiddleware(AgentMiddleware):
    """Withdraws the planning tool once the model is only re-planning.

    The planning tool returns no information, so consecutive writes cannot be
    progress. Rather than erroring, the tool is dropped from the request for one call
    and a notice tells the model to act; the streak clears as soon as it calls anything
    else, so a run that legitimately re-plans between steps is untouched.

    This targets deepagents' built-in ``write_todos``. A surface with its own persisted
    planning tool is unaffected.
    """

    def __init__(self, max_consecutive_planning_calls: int = MAX_CONSECUTIVE_PLANNING_CALLS):
        super().__init__()
        self.max_consecutive_planning_calls = max_consecutive_planning_calls

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        streak = _trailing_planning_calls(request.state.get("messages", []))
        if streak < self.max_consecutive_planning_calls:
            return handler(request)

        logger.warning(
            "Deep-agent called %s %s times in a row with no work in between; "
            "withdrawing the planning tool for this step.",
            PLANNING_TOOL_NAME,
            streak,
        )
        notice = HumanMessage(
            content=PLANNING_LOOP_NOTICE.format(tool_name=PLANNING_TOOL_NAME, count=streak)
        )
        # The notice rides this request only, never conversation state: same contract
        # as the forced-finalization notice above.
        return handler(
            request.override(
                messages=[*request.messages, notice],
                tools=[tool for tool in request.tools if tool_name(tool) != PLANNING_TOOL_NAME],
            )
        )


def build_hard_limit_middleware(
    structured_tool_name: Optional[str] = None,
    limits: DeepAgentLimits = DEFAULT_LIMITS,
) -> List[AgentMiddleware]:
    """The middleware stack enforcing the per-run soft and hard limits.

    ``structured_tool_name`` is the response_format schema's tool name, used to
    recognize its parse-failure ToolMessages and to address it in the forced-
    finalization notice. ``None`` for a surface whose result is written by tools, which
    should declare ``limits.finalize_tools`` instead. ``limits`` sizes the boundaries;
    the stack itself is always present.
    """
    return [
        ModelCallLimitMiddleware(run_limit=limits.max_model_calls, exit_behavior="error"),
        HardLimitsMiddleware(
            structured_tool_name=structured_tool_name,
            soft_run_timeout_seconds=limits.soft_timeout_seconds,
            run_timeout_seconds=limits.timeout_seconds,
            soft_token_budget=limits.soft_token_budget,
            hard_token_budget=limits.hard_token_budget,
            soft_model_calls=limits.soft_model_calls,
            max_consecutive_failures=limits.max_consecutive_structured_output_failures,
            finalize_tools=limits.finalize_tools,
        ),
        PlanningLoopMiddleware(
            max_consecutive_planning_calls=limits.max_consecutive_planning_calls
        ),
    ]
