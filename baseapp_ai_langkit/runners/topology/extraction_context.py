from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from django.db import connections
from langchain_core.language_models import BaseLanguageModel
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver


class TopologyExtractionAudit:
    """Counts side-effect attempts during topology extraction.

    The CI audit fixture asserts both counters stayed at zero per rule 9.
    """

    __slots__ = ("llm_calls", "db_writes")

    def __init__(self) -> None:
        self.llm_calls = 0
        self.db_writes = 0


def _build_raising_llm(audit: TopologyExtractionAudit) -> BaseLanguageModel:
    """Return a chat-model stub bound to `audit`. Any call raises and counts."""

    class _RaisingTopologyLLM(FakeChatModel):
        def _generate(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

        async def _agenerate(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

        def invoke(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

        async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

        def stream(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

        async def astream(self, *args: Any, **kwargs: Any) -> Any:
            audit.llm_calls += 1
            raise RuntimeError("LLM call during topology extraction")

    return _RaisingTopologyLLM()


@dataclass
class TopologyExtractionContext:
    """Bundle yielded by `topology_extraction_context()`."""

    llm: BaseLanguageModel
    config: RunnableConfig
    checkpointer: MemorySaver
    audit: TopologyExtractionAudit


def _make_db_write_counter(audit: TopologyExtractionAudit):
    write_keywords = ("INSERT", "UPDATE", "DELETE")

    def execute_wrapper(execute, sql, params, many, context):
        if isinstance(sql, str) and sql.lstrip().upper().startswith(write_keywords):
            audit.db_writes += 1
        return execute(sql, params, many, context)

    return execute_wrapper


@contextmanager
def topology_extraction_context() -> Iterator[TopologyExtractionContext]:
    """Yield safe inputs for shadow-compiling a runner's workflow.

    The caller passes these into `runner_class.build_topology_workflow(...)`:
        * llm: a stub chat model that raises on any invocation
        * config: a stub RunnableConfig with thread_id="topology-extraction"
        * checkpointer: an in-memory MemorySaver (never Postgres)
        * audit: counters for LLM-call and DB-write attempts (test-only)

    No LLM-client factory monkey-patching is required: the runner controls
    workflow construction, so passing safe inputs is sufficient.
    """
    audit = TopologyExtractionAudit()
    llm = _build_raising_llm(audit)
    config: RunnableConfig = {"configurable": {"thread_id": "topology-extraction"}}
    checkpointer = MemorySaver()
    write_wrapper = _make_db_write_counter(audit)

    with connections["default"].execute_wrapper(write_wrapper):
        yield TopologyExtractionContext(
            llm=llm,
            config=config,
            checkpointer=checkpointer,
            audit=audit,
        )
