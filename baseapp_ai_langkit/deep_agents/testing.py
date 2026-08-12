"""A scripted chat model, so a whole deep-agent graph run is deterministic in tests.

A deep agent is otherwise only testable one middleware at a time: its interesting
behaviours (a gate rejecting a call, a completion rule refusing to finish, a limit
forcing finalization) are all statements about what happens when the model does a
specific thing, and the only cheap way to make a model do a specific thing is to
script it.

Usage::

    model = ScriptedChatModel([
        ScriptedTurn(tool_calls=[("search_document", {"query": "annuitant"})]),
        ScriptedTurn(text="done"),
    ])

Each entry is consumed in order; running past the end repeats the last turn, which
keeps a graph that loops one step longer than expected from raising an opaque
StopIteration. Set ``repeat_last=False`` to fail loudly instead.

Every call records the tool names it was bound with on :attr:`bound_tool_names`, which
is how a test asserts that a middleware withheld a tool without reaching into the
graph's internals.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

#: (tool name, arguments) for one scripted tool call.
ToolCallSpec = Tuple[str, Dict[str, Any]]


@dataclass
class ScriptedTurn:
    """One model response: some tool calls, some text, or both."""

    tool_calls: Sequence[ToolCallSpec] = ()
    text: str = ""
    #: Provider stop reason, so a test can reproduce the max_tokens truncation shape.
    stop_reason: str = "tool_use"
    #: Token accounting reported for this call, so budget limits can be exercised
    #: without burning real tokens.
    input_tokens: int = 0
    output_tokens: int = 0


class ScriptedChatModel(BaseChatModel):
    """A chat model that replays a fixed script instead of calling a provider."""

    script: List[ScriptedTurn] = []
    repeat_last: bool = True
    #: Tool names bound on each call, in call order. Populated as the run proceeds.
    bound_tool_names: List[List[str]] = []
    #: The messages received on each call, in call order.
    received_messages: List[List[BaseMessage]] = []
    calls: int = 0

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, script: Sequence[ScriptedTurn], repeat_last: bool = True, **kwargs: Any):
        super().__init__(**kwargs)
        self.script = list(script)
        self.repeat_last = repeat_last
        self.bound_tool_names = []
        self.received_messages = []
        self.calls = 0
        self._bound_names: List[str] = []

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        """Record the bound tool names and return self, so the script keeps its state.

        Returning ``self`` rather than a copy is what makes ``bound_tool_names`` a
        record of the whole run: langchain rebinds tools on every model request, and a
        copy would reset the script position each time.
        """
        self._bound_names = [_name_of(tool) for tool in tools]
        return self

    def _next_turn(self) -> ScriptedTurn:
        if self.calls < len(self.script):
            return self.script[self.calls]
        if self.repeat_last and self.script:
            return self.script[-1]
        raise AssertionError(
            f"ScriptedChatModel ran out of script after {self.calls} calls "
            f"({len(self.script)} turns scripted)."
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        turn = self._next_turn()
        self.bound_tool_names.append(list(self._bound_names))
        self.received_messages.append(list(messages))
        self.calls += 1
        message = AIMessage(
            content=turn.text,
            tool_calls=[
                {
                    "name": name,
                    "args": args,
                    "id": f"call-{self.calls}-{index}",
                    "type": "tool_call",
                }
                for index, (name, args) in enumerate(turn.tool_calls)
            ],
            response_metadata={"stop_reason": turn.stop_reason},
            usage_metadata={
                "input_tokens": turn.input_tokens,
                "output_tokens": turn.output_tokens,
                "total_tokens": turn.input_tokens + turn.output_tokens,
            },
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _name_of(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name", ""))
    return str(getattr(tool, "name", "") or getattr(tool, "__name__", ""))


@dataclass
class RecordedCalls:
    """Helper for asserting which tools a run actually called, in order."""

    names: List[str] = field(default_factory=list)

    @classmethod
    def from_messages(cls, messages: Sequence[Any]) -> "RecordedCalls":
        return cls(names=[call["name"] for call in _iter_calls(messages)])


def _iter_calls(messages: Sequence[Any]) -> Iterator[Dict[str, Any]]:
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            yield call
