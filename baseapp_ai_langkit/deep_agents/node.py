"""LangGraphDeepAgent: the configurable deep-agent node.

A sibling of langkit's ``LangGraphAgent`` and ``MessagesWorker``. It implements
``LLMNodeInterface`` directly because the agent loop, planning, skills and virtual
filesystem all come from ``deepagents.create_deep_agent`` rather than from
``create_react_agent``, but it carries a ``state_modifier_schema`` like any other
node, so its behavioural prompt is admin-editable through the runner tables.

It does not own a checkpointer: whoever runs it owns memory, and a background job is
single-shot.

This base class holds no product knowledge and no tracing backend. Each surface
subclasses it and pins the class attributes and hooks: what tools the agent gets,
whether the run ends in a validated answer object or in whatever its tools wrote,
which skills it may discover, and what to do with the run's telemetry.
"""

import logging
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Type

from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.deep_agents import builder
from baseapp_ai_langkit.deep_agents.limits import (
    DEFAULT_LIMITS,
    DeepAgentLimitError,
    DeepAgentLimits,
    describe_last_model_turn,
    model_call_count,
    spent_tokens,
)
from baseapp_ai_langkit.deep_agents.skills.files import build_skill_files
from baseapp_ai_langkit.deep_agents.skills.sources import EmptySkillSource, SkillSource
from baseapp_ai_langkit.deep_agents.telemetry.cache import cache_usage
from baseapp_ai_langkit.deep_agents.telemetry.skills import skills_read
from baseapp_ai_langkit.deep_agents.tool_scoping import FILESYSTEM_BROWSING_TOOLS

logger = logging.getLogger(__name__)


class DeepAgentNodeError(Exception):
    """Raised when the deep-agent run fails for a reason that is not a limit."""


class LangGraphDeepAgent(LLMNodeInterface):
    """Single-node deep agent: tools, and optionally skills, in one deepagents loop.

    Subclass and set the class attributes; the base class makes no product decision.
    """

    usage_prompt_schema = BasePromptSchema(
        description="Describes the deep agent node.",
        prompt=(
            "Single root agent that fulfils one request by selecting its own tools, "
            "reading skills on demand, and working until its task is done."
        ),
    )

    #: The run's final answer schema, emitted as a structured tool call and parsed by
    #: LangGraph into ``state["structured_response"]``. ``None`` for a surface whose
    #: result is written by its tools rather than returned as one object.
    response_format: Optional[Type[BaseModel]] = None
    #: Per-run resource boundaries. The governor middleware is always built (in
    #: :func:`builder.build_deep_agent`); subclasses only size it for their surface.
    limits: DeepAgentLimits = DEFAULT_LIMITS
    #: Skill directories the skills middleware may discover. ``None`` exposes every
    #: skill the source has; an empty iterable exposes none.
    skill_names: Optional[Iterable[str]] = ()
    #: Span name for the run, used when the runnable config does not name one.
    run_name: str = "deep_agent"

    def __init__(self, *args, **kwargs):
        self._agent = None
        self._skill_files_cache: Optional[Dict[str, Any]] = None
        #: The whole result state of the last run, for a caller that needs more than
        #: the reply message (the tool calls made, the raw messages).
        self.last_result: Optional[Dict[str, Any]] = None
        #: The last run's telemetry, as handed to :meth:`on_run_complete`.
        self.last_metrics: Dict[str, Any] = {}
        super().__init__(*args, **kwargs)

    # --- What the surface provides -------------------------------------------------

    def get_agent_tools(self) -> Sequence[BaseTool]:
        """The tools this run exposes. Subclasses override; the default is none."""
        return ()

    def get_skill_source(self) -> SkillSource:
        """Where this run's skills come from. The default is a source with none."""
        return EmptySkillSource()

    def get_skill_context(self) -> Mapping[str, Any]:
        """Condition context used to specialize skill components for this run."""
        return {}

    def get_initial_state(self) -> Dict[str, Any]:
        """Extra keys merged into the agent's invoke payload beyond messages and files."""
        return {}

    def get_excluded_tools(self) -> Iterable[str]:
        """Built-in tools to withhold, derived from whether this surface has skills.

        Skills are read THROUGH the filesystem tools (the skills middleware publishes
        ``/skills/**`` and contributes no tools of its own), so a node exposing no
        skills has an empty virtual filesystem and nothing for ``ls``/``glob``/``grep``
        to find. Offering them anyway invites a browse loop that costs a full context
        re-read per attempt. Override to keep them, or to drop more.
        """
        if not self._skill_files():
            return FILESYSTEM_BROWSING_TOOLS
        return ()

    # --- What the surface does with the outcome ------------------------------------

    def extract_answer(self, state: Mapping[str, Any]) -> Optional[BaseModel]:
        """Pull the run's structured answer. ``None`` aborts the run.

        Only called when :attr:`response_format` is set. Subclasses may override to
        degrade differently, for instance falling back to the last assistant text.
        """
        return builder.extract_answer(dict(state), self.response_format)

    def build_result_message(
        self, answer: Optional[BaseModel], result: Mapping[str, Any]
    ) -> AIMessage:
        """How the run's outcome enters caller state.

        With an answer schema the default is its JSON dump as content, with the typed
        object riding ``additional_kwargs`` so callers can read it back without
        re-parsing. Without one there is no object to dump, so the last assistant text
        stands in; a surface whose real product is what its tools wrote generally
        ignores this message entirely.
        """
        if answer is not None:
            return AIMessage(
                content=answer.model_dump_json(),
                additional_kwargs={"structured_response": answer},
            )
        return AIMessage(content=builder.extract_last_text(result.get("messages", []) or []))

    def extra_trace_metadata(self, result: Mapping[str, Any]) -> Dict[str, Any]:
        """Extra telemetry derived from the run's outcome, merged into the metrics."""
        return {}

    def on_run_complete(self, metrics: Dict[str, Any], result: Mapping[str, Any]) -> None:
        """Called once a run finishes, with its telemetry.

        The base class only logs (see :meth:`_run`). This hook is where a surface
        pushes the numbers wherever it keeps them: onto a trace, onto a database row,
        into a metrics backend. Deliberately not a tracing-backend call here, so this
        package depends on no particular one.
        """

    # --- Execution -----------------------------------------------------------------

    def invoke(self, messages: List[AnyMessage], state=None, *args, **kwargs) -> AIMessage:
        """Run one deep-agent run and return its result message."""
        return self._run(messages)

    def _run(self, messages: List[AnyMessage]) -> AIMessage:
        started = time.monotonic()
        try:
            result = self._get_agent().invoke(
                {
                    "messages": messages,
                    "files": self._skill_files(),
                    **self.get_initial_state(),
                },
                # recursion_limit overrides langchain's compiled-in 10_000: the
                # super-step backstop behind the per-run caps in `limits`.
                config={**(self.config or {}), "recursion_limit": self.limits.recursion_limit},
            )
        except DeepAgentLimitError:
            # Controlled abort: a per-run hard limit fired. Keep the typed error so
            # callers can branch on it, rather than reporting an undifferentiated
            # failure they would then retry.
            logger.error("Deep-agent run hit a hard limit (%s)", self.run_name, exc_info=True)
            raise
        except (ModelCallLimitExceededError, GraphRecursionError) as exc:
            # Same contract for the library-raised caps: normalize them into the limit
            # error family so a caller has one exception type to branch on.
            logger.error("Deep-agent run hit a hard limit (%s)", self.run_name, exc_info=True)
            raise DeepAgentLimitError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Deep-agent run failed (%s)", self.run_name)
            raise DeepAgentNodeError(str(exc)) from exc

        self.last_result = result
        result_messages = result.get("messages", []) or []
        metrics = self._build_metrics(result, result_messages, time.monotonic() - started)
        self.last_metrics = metrics
        logger.info("Deep-agent run finished (%s): %s", self.run_name, metrics)
        self.on_run_complete(metrics, result)

        answer = None
        if self.response_format is not None:
            answer = self.extract_answer(result)
            if answer is None:
                # What the model did instead goes in the message: the bare version of
                # this error does not say whether the provider ignored tool_choice,
                # called the wrong tool, or was cut off mid-answer.
                raise DeepAgentNodeError(
                    "Deep agent produced no final answer "
                    f"({describe_last_model_turn(result_messages)})"
                )
        return self.build_result_message(answer, result)

    def _build_metrics(
        self,
        result: Mapping[str, Any],
        result_messages: List[AnyMessage],
        elapsed_seconds: float,
    ) -> Dict[str, Any]:
        """The run's telemetry: what it cost and which skills it actually loaded."""
        skills_used = skills_read(result_messages)
        return {
            "skills_used": skills_used,
            "skills_used_count": len(skills_used),
            "model_calls": model_call_count(result_messages),
            "total_tokens": spent_tokens(result_messages),
            "elapsed_seconds": round(elapsed_seconds, 3),
            **cache_usage(result_messages),
            **self.extra_trace_metadata(result),
        }

    def _get_agent(self):
        # No checkpointer: the caller owns memory, or the run is single-shot.
        if self._agent is None:
            self._agent = builder.build_deep_agent(
                model=self.llm,
                tools=self.get_agent_tools(),
                system_prompt=self.build_system_prompt(),
                response_format=self.response_format,
                limits=self.limits,
                has_skills=bool(self._skill_files()),
                excluded_tools=self.get_excluded_tools(),
            )
        return self._agent

    def _skill_files(self) -> Dict[str, Any]:
        """The virtual-filesystem payload for this run, built once and reused.

        Built once rather than per call because it is read three times during a single
        build (to decide whether to advertise the skills root, to decide which built-in
        tools to withhold, and to seed the agent's state) and a fresh dict per read
        would make those three disagree if the source changed underneath them.
        """
        if self._skill_files_cache is None:
            self._skill_files_cache = build_skill_files(
                self.get_skill_source(),
                skill_names=None if self.skill_names is None else list(self.skill_names),
                context=self.get_skill_context(),
            )
        return self._skill_files_cache

    def build_system_prompt(self) -> Optional[str]:
        """Render the (possibly admin-overridden) state modifiers to a single string.

        Mirrors how ``LangGraphAgent`` turns its state modifiers into system messages,
        but deepagents takes one ``system_prompt`` string, so the rendered messages are
        joined. Returns ``None`` when the subclass declares no schema.
        """
        system_messages = self.get_state_modifier_system_message()
        if system_messages:
            return "\n\n".join(message.content for message in system_messages)
        return None
