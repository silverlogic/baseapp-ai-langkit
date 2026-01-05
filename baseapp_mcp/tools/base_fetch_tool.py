"""
Abstract fetch tool for MCP servers.

This tool provides a generic fetch interface that can be configured with
custom fetch and content processing functions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Annotated, Any

from baseapp_mcp import exceptions
from baseapp_mcp.tools.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


class BaseFetchTool(MCPTool, ABC):
    """
    Generic fetch tool that accepts fetch, content processing and document building functions.
    """

    name: str = "fetch"
    description: str = "Fetch a document by its search term."

    def tool_func_core(
        self, search_term: Annotated[str, "Search term to fetch the document."]
    ) -> dict[str, Any]:
        if not search_term:
            raise exceptions.MCPValidationError("Search term cannot be empty or whitespace.")

        try:
            document = self.fetch(search_term)
        except Exception as e:
            logger.error(f"Error fetching document '{search_term}': {e}")
            raise exceptions.MCPDataError(f"Document '{search_term}' not found.")

        # Process content
        content = self.content_processor(document)

        # Build document dict
        doc = self.doc_builder(document, content)

        return doc

    @abstractmethod
    def fetch(self, search_term: str) -> Any:
        """
        Abstract method that takes a document ID and returns a document object.

        Args:
            search_term: Search term to fetch the document (can be ID, title, URL, etc.)
        Returns:
            Document object
        """
        pass

    def content_processor(self, document: Any) -> str:
        """
        Function that takes a document and returns plain text content.
        By default it assumes document has a 'html' attribute and uses strip_html_tags.
        Override this method to provide a custom content processor.

        Args:
            document: Document object
        Returns:
            Plain text content
        """
        html_content = getattr(document, "html", None)
        if html_content:
            try:
                from baseapp_ai_langkit.embeddings.context_utils import strip_html_tags

                return strip_html_tags(html_content)
            except ImportError:
                pass

        return str(document)

    def doc_builder(self, document: Any, content: str) -> dict[str, Any]:
        """
        Function that takes (document, content) and returns a dictionary.
        By default it uses the page_id, page_title, url and content to build the document.
        Override this method to provide a custom document builder.

        Args:
            document: Document object
            content: Plain text content
        Returns:
            Document dictionary
        """
        doc = {
            "id": getattr(document, "page_id", getattr(document, "id", "")),
            "title": getattr(document, "page_title", getattr(document, "title", "")),
            "text": content,
            "url": getattr(document, "url", None),
        }
        return doc

    def simplify_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Simplify the response for logging purposes.

        Args:
            response: The full response dictionary.
        Returns:
            A simplified version of the response.
        """
        text = response.get("text", "")
        simplified = {
            "id": response.get("id"),
            "title": response.get("title"),
            "text": text[:200] + "..." if len(text) > 200 else text,
            "url": response.get("url"),
        }
        return simplified
