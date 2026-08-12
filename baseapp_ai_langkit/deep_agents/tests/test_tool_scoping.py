"""Unit tests for withholding built-in tools from the model."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from baseapp_ai_langkit.deep_agents.tool_scoping import (
    FILESYSTEM_BROWSING_TOOLS,
    ExcludedToolsMiddleware,
    tool_name,
)


def _named_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _request(tools) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=[HumanMessage("q")],
        state={},
        runtime=None,
        tools=tools,
    )


def _run(middleware: ExcludedToolsMiddleware, tools) -> ModelRequest:
    seen = {}

    def handler(request: ModelRequest) -> ModelResponse:
        seen["request"] = request
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(_request(tools), handler)
    return seen["request"]


class ToolNameTests(SimpleTestCase):
    def test_reads_a_base_tool_and_a_dict_spec(self):
        self.assertEqual(tool_name(_named_tool("ls")), "ls")
        self.assertEqual(tool_name({"name": "grep"}), "grep")

    def test_returns_none_for_an_unnamed_tool(self):
        self.assertIsNone(tool_name({}))
        self.assertIsNone(tool_name({"name": 3}))


class ExcludedToolsMiddlewareTests(SimpleTestCase):
    def test_drops_the_named_tools(self):
        tools = [_named_tool("ls"), _named_tool("read_file")]
        kept = _run(ExcludedToolsMiddleware({"ls"}), tools)
        self.assertEqual([tool.name for tool in kept.tools], ["read_file"])

    def test_an_empty_exclusion_passes_the_request_through_untouched(self):
        tools = [_named_tool("ls")]
        request = _request(tools)
        seen = {}

        def handler(received: ModelRequest) -> ModelResponse:
            seen["request"] = received
            return ModelResponse(result=[AIMessage(content="ok")])

        ExcludedToolsMiddleware(()).wrap_model_call(request, handler)
        self.assertIs(seen["request"], request)

    def test_an_exclusion_that_matches_nothing_passes_the_request_through(self):
        tools = [_named_tool("ls")]
        request = _request(tools)
        seen = {}

        def handler(received: ModelRequest) -> ModelResponse:
            seen["request"] = received
            return ModelResponse(result=[AIMessage(content="ok")])

        ExcludedToolsMiddleware({"grep"}).wrap_model_call(request, handler)
        self.assertIs(seen["request"], request)

    def test_read_file_is_not_in_the_browsing_set(self):
        """It is the escape hatch for evicted oversized payloads, not a browse tool."""
        self.assertNotIn("read_file", FILESYSTEM_BROWSING_TOOLS)
        self.assertIn("ls", FILESYSTEM_BROWSING_TOOLS)
