"""The single construction point for a deepagents root agent.

Product-agnostic by design: every consumer (an interactive node, a background job
runner, an eval harness) builds the same agent the same way, model plus tools plus
middleware plus optional structured output. What varies is passed in: the tools, the
system prompt, the limit profile, the skills, and whether the run ends in a validated
answer object or in whatever its tools wrote. No product decision is made here.

The one thing a caller cannot do is opt out of the limit governors. They are built
here and appended ahead of any caller middleware, because they are the guardrails
against a runaway loop and a surface that could forget them would eventually forget
them.
"""

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Type, Union

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ValidationError

from baseapp_ai_langkit.deep_agents.limits import (
    DEFAULT_LIMITS,
    DeepAgentLimits,
    RunBudget,
    build_hard_limit_middleware,
)
from baseapp_ai_langkit.deep_agents.skills.files import SKILLS_ROOT
from baseapp_ai_langkit.deep_agents.tool_scoping import ExcludedToolsMiddleware

logger = logging.getLogger(__name__)


def build_deep_agent(
    model: BaseLanguageModel,
    tools: Sequence[BaseTool],
    *,
    system_prompt: Optional[str] = None,
    response_format: Optional[Union[Type[BaseModel], ToolStrategy]] = None,
    limits: DeepAgentLimits = DEFAULT_LIMITS,
    skills_root: str = SKILLS_ROOT,
    has_skills: bool = False,
    excluded_tools: Iterable[str] = (),
    checkpointer: Any = None,
    extra_middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[Mapping[str, Any]] = (),
    budget: Optional[RunBudget] = None,
):
    """Build a deepagents root agent.

    ``response_format`` is the pydantic schema of a final answer, emitted by the last
    step as a tool call and parsed by LangGraph into ``state["structured_response"]``.
    A caller that already wrapped its schema in a ``ToolStrategy`` may pass that
    instead; it is used as-is rather than wrapped a second time, which would produce a
    strategy whose schema is another strategy and fail as soon as anything reads the
    schema's name. Pass ``None`` for a surface whose result is written by its tools:
    there is then no final answer to validate, and the surface's own completion rules
    decide whether the run produced anything. Such a surface should declare
    ``limits.finalize_tools`` so a soft-limit breach can still force it to finish.

    ``has_skills`` controls whether the skills root is advertised at all. Advertising
    an empty root invites a browse loop that costs a full context re-read per attempt,
    so a surface with nothing mounted says so.

    ``excluded_tools`` names built-in tools to withhold from the model, which is the
    only way to drop the ones deepagents' own middleware injects since that middleware
    cannot be skipped (see :mod:`.tool_scoping`). Mechanism only: which tools a surface
    has no use for is the caller's decision.

    ``checkpointer`` is ``None`` when an outer workflow owns memory or the run is
    single-shot; pass a saver when the agent should persist its own thread.

    ``subagents`` are deepagents ``SubAgent`` specs, reachable through the ``task`` tool. The
    limit governors are injected into each one, sharing a :class:`RunBudget` with the root, so a
    fan-out draws down the same pool instead of going uncounted.

    A surface whose tools write anything should declare its own ``general-purpose`` spec.
    ``create_deep_agent`` always installs one, and a subagent that declares no tools inherits
    the parent's, so by default an isolated context can call whatever the root can. Naming a
    spec ``general-purpose`` replaces deepagents' own. Not defaulted here, because which tools
    are safe to delegate is the caller's decision.
    """
    # Lazy import so the module stays importable on a host without deepagents.
    from deepagents import create_deep_agent

    strategy: Optional[ToolStrategy] = None
    if response_format is not None:
        strategy = (
            response_format
            if isinstance(response_format, ToolStrategy)
            else ToolStrategy(schema=response_format)
        )

    # Appended before caller middleware but after deepagents' own tool-injecting
    # middleware, which is what lets the exclusion middleware strip filesystem tools
    # the surface cannot use.
    middleware: List[AgentMiddleware] = build_hard_limit_middleware(
        strategy.schema.__name__ if strategy is not None else None,
        limits=limits,
        budget=budget,
    )
    if excluded := frozenset(excluded_tools):
        middleware.append(ExcludedToolsMiddleware(excluded))
    middleware.extend(extra_middleware)

    return create_deep_agent(
        model=model,
        tools=list(tools),
        system_prompt=system_prompt,
        skills=[skills_root] if has_skills else [],
        checkpointer=checkpointer,
        response_format=strategy,
        # Hard per-run caps on model calls, wall clock, tokens and the structured-output
        # retry streak. Without these the agent retries parse failures unboundedly under
        # langchain's compiled-in recursion_limit of 10_000.
        middleware=middleware,
        # None rather than an empty list: passing the argument at all reads as "this surface
        # delegates" when it does not.
        subagents=governed_subagents(subagents, limits=limits, budget=budget) or None,
    )


def governed_subagents(
    subagents: Sequence[Mapping[str, Any]],
    limits: DeepAgentLimits = DEFAULT_LIMITS,
    budget: Optional[RunBudget] = None,
) -> List[Dict[str, Any]]:
    """Each declared subagent spec with the limit governors prepended to its middleware.

    Prepended, so the governors see a request before any middleware the spec brought itself.

    Only declarative specs are touched. A ``CompiledSubAgent`` was built with its middleware
    already decided and an ``AsyncSubAgent`` runs elsewhere, so both pass through untouched and
    spend outside the pool.
    """
    prepared: List[Dict[str, Any]] = []
    for spec in subagents:
        if "runnable" in spec or "graph_id" in spec:
            prepared.append(dict(spec))
            continue
        prepared.append(
            {
                **spec,
                "middleware": [
                    *build_hard_limit_middleware(None, limits=limits, budget=budget, is_root=False),
                    *spec.get("middleware", []),
                ],
            }
        )
    return prepared


def stringify_content(content: Any) -> str:
    """Flatten a message's content (str or list-of-blocks) to plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def extract_last_text(messages: Sequence[Any]) -> str:
    """The text of the last assistant message, or an empty string."""
    for message in reversed(messages):
        kind = getattr(message, "type", None) or getattr(message, "role", "")
        if kind in ("ai", "assistant"):
            text = stringify_content(getattr(message, "content", ""))
            if text:
                return text
    return ""


def extract_answer(state: Dict[str, Any], schema: Type[BaseModel]) -> Optional[BaseModel]:
    """Pull a run's structured answer out of its result state.

    With ``response_format=schema`` the final step lands a parsed object under
    ``structured_response``. LangGraph normally returns the pydantic instance, but a
    looser strategy may land a dict, which is coerced. Returns ``None`` when the
    structured output is missing or malformed: how to degrade is the caller's decision,
    since a chat surface may fall back to the last assistant text while a batch runner
    must fail rather than fabricate a shell object.
    """
    structured = state.get("structured_response")
    if isinstance(structured, schema):
        return structured
    if isinstance(structured, dict):
        try:
            return schema.model_validate(structured)
        except ValidationError:
            logger.warning("structured_response was a malformed mapping for %s", schema.__name__)
    return None
