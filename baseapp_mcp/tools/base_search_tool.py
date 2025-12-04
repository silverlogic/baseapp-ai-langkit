"""
Abstract search tool for MCP servers.

This tool provides a generic search interface that can be configured with
a custom search function via the search_function parameter.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from baseapp_mcp import exceptions
from baseapp_mcp.tools.base_mcp_tool import MCPTool

logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    query: str = Field(description="The search query to find relevant content")


class BaseSearchTool(MCPTool, ABC):
    """
    Generic search tool that accepts a search function.

    The search function should accept a query string and return a list of results.
    Each result should be a dict with at least 'id', 'title', and optionally 'text', 'url'.
    """

    name: str = "search"
    description: str = "Search documents by semantic similarity to find relevant documents."
    args_schema = SearchInput

    def __init__(self, *args, **kwargs):
        """
        Initialize BaseSearchTool with user identifier.
        """
        if "uses_transformer_calls" not in kwargs:
            kwargs["uses_transformer_calls"] = True

        super().__init__(*args, **kwargs)

    def tool_func_core(self, query: str) -> dict[str, Any]:
        if not query or not query.strip():
            raise exceptions.MCPValidationError("Query cannot be empty or whitespace.")

        results = self.search(query.strip())
        self.add_transformer_calls()
        logger.info(f"Search returned {len(results)} results")

        return {"results": results}

    @abstractmethod
    def search(self, query: str) -> list[dict[str, Any]]:
        """
        Abstract method that takes a query string and returns a list of result dicts.
        """
        pass
