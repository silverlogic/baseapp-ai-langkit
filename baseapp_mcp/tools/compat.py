"""Compatibility layer for baseapp_ai_langkit integration."""

# TODO: Think about a better way to handle this coupling between baseapp_mcp and baseapp_ai_langkit

from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from baseapp_ai_langkit.base.tools.inline_tool import InlineTool


def get_inline_tool_class() -> Optional[Type["InlineTool"]]:
    """
    Get InlineTool class from baseapp_ai_langkit if available.

    Returns:
        InlineTool class if baseapp_ai_langkit is available, None otherwise
    """
    try:
        from baseapp_ai_langkit.base.tools.inline_tool import InlineTool

        return InlineTool
    except ImportError:
        return None


def create_mcp_tool_base_class():
    """
    Create the base class for MCPTool that optionally inherits from InlineTool.

    This function dynamically creates a base class that inherits from InlineTool
    if baseapp_ai_langkit is available, allowing MCP tools to be used in agents.

    Returns:
        Base class for MCPTool
    """
    from baseapp_mcp.tools.base_tool import BaseMCPToolInterface

    InlineTool = get_inline_tool_class()

    if InlineTool is not None:
        # Create a class that inherits from both InlineTool and BaseMCPToolInterface
        # This allows isinstance checks to work correctly with InlineTool
        class MCPToolBase(InlineTool, BaseMCPToolInterface):
            """
            Base class for MCP tools that is compatible with InlineTool.

            This class allows MCP tools to be used in baseapp_ai_langkit agents
            that expect InlineTool instances.
            """

            pass

        return MCPToolBase
    else:
        # baseapp_ai_langkit not available, use only BaseMCPToolInterface
        return BaseMCPToolInterface


def is_inline_tool_compatible(tool_instance) -> bool:
    """
    Check if a tool instance is compatible with InlineTool.

    Args:
        tool_instance: Tool instance to check

    Returns:
        True if the tool can be used as InlineTool, False otherwise
    """
    InlineTool = get_inline_tool_class()
    if InlineTool is None:
        return False

    # Check if instance is an InlineTool or has the required interface
    return isinstance(tool_instance, InlineTool) or (
        hasattr(tool_instance, "name")
        and hasattr(tool_instance, "description")
        and hasattr(tool_instance, "tool_func")
        and hasattr(tool_instance, "to_langchain_tool")
    )
