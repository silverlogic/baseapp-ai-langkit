"""
Abstract search tool for MCP servers.

This tool provides a generic search interface that can be configured with
a custom search function via the search_function parameter.
"""

import logging
from typing import Any, Callable, Dict

from pydantic import BaseModel, Field

from baseapp_mcp import exceptions
from baseapp_mcp.tools.base_mcp_tool import MCPTool

logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    query: str = Field(description="The search query to find relevant content")


class SearchTool(MCPTool):
    """
    Generic search tool that accepts a search function.

    The search function should accept a query string and return a list of results.
    Each result should be a dict with at least 'id', 'title', and optionally 'text', 'url'.
    """

    name: str = "search"
    description: str = "Search documents by semantic similarity to find relevant documents."
    args_schema = SearchInput

    def __init__(
        self,
        user_identifier: str,
        search_function: Callable[[str], list[Dict[str, Any]]] | None = None,
    ):
        """
        Initialize SearchTool with user identifier and optional search function.

        Args:
            user_identifier: Identifier for the user
            search_function: Optional function that takes a query string and returns
                           a list of result dicts. If not provided, must be set via
                           configure_search_function before use.
        """
        super().__init__(user_identifier, uses_transformer_calls=True)
        self._search_function = search_function

    def configure_search_function(self, search_function: Callable[[str], list[Dict[str, Any]]]):
        """
        Configure the search function to use.

        Args:
            search_function: Function that takes a query string and returns a list of result dicts
        """
        self._search_function = search_function

    def tool_func_core(self, query: str) -> Dict[str, Any]:
        if not query or not query.strip():
            raise exceptions.MCPValidationError("Query cannot be empty or whitespace.")

        if self._search_function is None:
            raise exceptions.MCPConfigurationError(
                "Search function not configured. Call configure_search_function() or "
                "provide search_function in __init__."
            )

        results = self._search_function(query.strip())
        self.add_transformer_calls()
        logger.info(f"Search returned {len(results)} results")

        return {"results": results}
