"""Base tool interface for MCP tools."""

from abc import ABC, abstractmethod
from typing import Optional, Type

from pydantic import BaseModel


class BaseMCPToolInterface(ABC):
    """
    Base interface for MCP tools that can be used independently or with baseapp_ai_langkit.

    This interface is compatible with baseapp_ai_langkit's AbstractBaseTool/InlineTool
    to allow MCP tools to be used in agents.
    """

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        args_schema: Optional[Type[BaseModel]] = None,
    ):
        """
        Initialize the tool with optional overrides.

        Args:
            name: Tool name (overrides class attribute if provided)
            description: Tool description (overrides class attribute if provided)
            args_schema: Pydantic model for tool arguments (overrides class attribute if provided)
        """
        if name:
            self.name = name
        if description:
            self.description = description
        if args_schema:
            self.args_schema = args_schema

    @abstractmethod
    def tool_func(self, *args, **kwargs):
        """
        Execute the tool with given arguments.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tool execution result
        """
        pass

    @abstractmethod
    def to_langchain_tool(self):
        """
        Convert the tool to a LangChain tool for use in agents.

        Returns:
            LangChain Tool instance
        """
        pass
