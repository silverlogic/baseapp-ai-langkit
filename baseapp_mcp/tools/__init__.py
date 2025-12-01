"""MCP Tools package."""

from baseapp_mcp.tools.base_mcp_tool import MCPTool
from baseapp_mcp.tools.base_tool import BaseMCPToolInterface
from baseapp_mcp.tools.compat import (
    create_mcp_tool_base_class,
    get_inline_tool_class,
    is_inline_tool_compatible,
)

__all__ = [
    "MCPTool",
    "BaseMCPToolInterface",
    "get_inline_tool_class",
    "is_inline_tool_compatible",
    "create_mcp_tool_base_class",
]
