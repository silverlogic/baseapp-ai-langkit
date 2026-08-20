"""Which of the deep agent's built-in tools a surface actually gets.

``create_deep_agent`` installs its filesystem middleware unconditionally, so every
build is handed ``ls``, ``read_file``, ``write_file``, ``edit_file``, ``glob``,
``grep`` and ``execute`` whether the surface has anything to read or not. There is
no flag to skip it. What there IS is the ``middleware`` hook the limit governors
already use: deepagents extends caller middleware *after* its own, so a
``wrap_model_call`` here sees the fully-assembled tool list and can drop names from
it before the model ever sees them.

Why bother: the filesystem is how skills are read (the skills middleware contributes
no tools of its own, it publishes ``/skills/**`` and relies on ``ls``/``glob``/
``read_file``). A surface with no skills has an empty virtual filesystem, so those
tools can only ever return nothing, and a model that keeps trying costs a full
uncached context re-read per attempt.

``read_file`` is deliberately NOT droppable. The filesystem middleware evicts oversized
payloads to the virtual filesystem and replaces them with "saved at <path>, read it
with read_file". A long document can cross that threshold, and without ``read_file``
the evicted content would be unreachable rather than merely large.
"""

import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Union,
)

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

#: The deepagents filesystem tools that only make sense when something is mounted on
#: the virtual filesystem. ``read_file`` is absent on purpose (see the module
#: docstring): it is the escape hatch for evicted oversized payloads, not a browse
#: tool, so it stays even when there is no skill to read.
FILESYSTEM_BROWSING_TOOLS: FrozenSet[str] = frozenset(
    {"ls", "glob", "grep", "write_file", "edit_file", "execute"}
)

#: What a surface keeps when it wants the virtual filesystem as a scratchpad rather
#: than as a place to read skills from. Writing notes across a long run is a real use
#: for an otherwise-empty filesystem: a surface that gathers more than it can hold in
#: one context can park findings in a file and read them back at the end.
#:
#: ``glob``, ``grep`` and ``execute`` stay withheld. The agent wrote these files, so it
#: knows their paths, and ``ls`` plus ``read_file`` is the whole vocabulary needed to
#: get them back. Each extra tool costs its schema in every request for a capability
#: nothing has asked for yet.
SCRATCHPAD_TOOLS: FrozenSet[str] = frozenset({"ls", "write_file", "edit_file"})


def tool_name(tool: Union[BaseTool, Dict[str, Any]]) -> Optional[str]:
    """The name of a bound tool, whether it arrives as a BaseTool or a dict spec."""
    if isinstance(tool, dict):
        name = tool.get("name")
    else:
        name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None


class ExcludedToolsMiddleware(AgentMiddleware):
    """Drops named tools from every model request.

    Placed after the tool-injecting middleware (deepagents appends caller middleware
    late), so it can remove middleware-provided tools the surface has no use for,
    which is the only way to get rid of them since their middleware cannot be skipped.

    Filtering the request rather than the middleware stack means the tools still exist
    server-side: anything already in conversation state keeps resolving, and the model
    simply stops being offered them.
    """

    def __init__(self, excluded: Iterable[str]) -> None:
        super().__init__()
        self.excluded = frozenset(excluded)

    def _filter(self, request: ModelRequest) -> ModelRequest:
        if not self.excluded:
            return request
        kept: List[Any] = [tool for tool in request.tools if tool_name(tool) not in self.excluded]
        if len(kept) == len(request.tools):
            return request
        return request.override(tools=kept)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._filter(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._filter(request))
