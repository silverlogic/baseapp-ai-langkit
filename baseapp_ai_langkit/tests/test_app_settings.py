import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from baseapp_mcp.app_settings import AppSettings


@pytest.fixture
def app_settings():
    return AppSettings("BASEAPP_AI_LANGKIT_")


class TestMCPToolListValidation:
    def test_no_overlap_returns_all_lists(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["b.ToolB"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=["c.ToolC"],
        ):
            assert app_settings.MCP_TOOLS == ["a.ToolA"]
            assert app_settings.DEBUG_MCP_TOOLS == ["b.ToolB"]
            assert app_settings.EXPERIMENTAL_MCP_TOOLS == ["c.ToolC"]

    def test_all_empty_is_valid(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=[],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=[],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=[],
        ):
            assert app_settings.MCP_TOOLS == []
            assert app_settings.DEBUG_MCP_TOOLS == []
            assert app_settings.EXPERIMENTAL_MCP_TOOLS == []

    def test_mcp_and_debug_overlap_raises(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=[],
        ):
            with pytest.raises(ImproperlyConfigured, match="MCP_TOOLS.*DEBUG_MCP_TOOLS"):
                app_settings.MCP_TOOLS

    def test_mcp_and_experimental_overlap_raises(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=[],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=["a.ToolA"],
        ):
            with pytest.raises(ImproperlyConfigured, match="MCP_TOOLS.*EXPERIMENTAL_MCP_TOOLS"):
                app_settings.EXPERIMENTAL_MCP_TOOLS

    def test_debug_and_experimental_overlap_raises(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=[],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["b.ToolB"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=["b.ToolB"],
        ):
            with pytest.raises(
                ImproperlyConfigured, match="DEBUG_MCP_TOOLS.*EXPERIMENTAL_MCP_TOOLS"
            ):
                app_settings.EXPERIMENTAL_MCP_TOOLS

    def test_overlap_detected_regardless_of_which_property_is_accessed(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["a.ToolA"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=[],
        ):
            with pytest.raises(ImproperlyConfigured):
                app_settings.DEBUG_MCP_TOOLS

            with pytest.raises(ImproperlyConfigured):
                app_settings.EXPERIMENTAL_MCP_TOOLS

    def test_error_message_includes_overlapping_entries(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA", "shared.ToolX"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["shared.ToolX"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=[],
        ):
            with pytest.raises(ImproperlyConfigured, match="shared.ToolX"):
                app_settings.MCP_TOOLS

    def test_multiple_overlapping_entries_all_reported(self, app_settings):
        with override_settings(
            BASEAPP_AI_LANGKIT_MCP_TOOLS=["a.ToolA", "b.ToolB"],
            BASEAPP_AI_LANGKIT_DEBUG_MCP_TOOLS=["a.ToolA", "b.ToolB"],
            BASEAPP_AI_LANGKIT_EXPERIMENTAL_MCP_TOOLS=[],
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                app_settings.MCP_TOOLS
            message = str(exc_info.value)
            assert "a.ToolA" in message or "b.ToolB" in message
