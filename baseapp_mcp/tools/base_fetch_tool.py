"""
Abstract fetch tool for MCP servers.

This tool provides a generic fetch interface that can be configured with
custom fetch and content processing functions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from baseapp_mcp import exceptions
from baseapp_mcp.tools import MCPTool

logger = logging.getLogger(__name__)


class FetchArgs(BaseModel):
    search_term: str = Field(..., description="Search term to fetch the document.")


class BaseFetchTool(MCPTool, ABC):
    """
    Generic fetch tool that accepts fetch, content processing and document building functions.
    """

    name: str = "fetch"
    description: str = "Fetch a document by its search term."
    args_schema = FetchArgs

    def tool_func_core(self, **kwargs) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        search_term = self.get_search_term(kwargs)
        if not search_term:
            raise exceptions.MCPValidationError("Document ID cannot be empty or whitespace.")

        try:
            document = self.fetch(search_term)
        except Exception as e:
            logger.error(f"Error fetching document {search_term}: {e}")
            raise exceptions.MCPDataError(f"Document with ID {search_term} not found.")

        # Process content
        content = self.content_processor(document)

        # Build document dict
        full_doc, simplified_doc = self.doc_builder(document, content)

        return full_doc, simplified_doc

    def get_search_term(self, kwargs: dict[str, Any]) -> str:
        """
        If you change the search_term field in the args_schema, you need to override this method.
        It's good practice to update the args_schema field so the LLM isn't confused by contradictory arguments.

        Returns:
            The search term from the arguments.
        """
        return kwargs.get("search_term", "").strip()

    @abstractmethod
    def fetch(self, search_term: str) -> Any:
        """
        Abstract method that takes a document ID and returns a document object.

        Args:
            id: Document ID
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

    def doc_builder(self, document: Any, content: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Function that takes (document, content) and returns (full_doc_dict, simplified_doc_dict).
        By default it uses the page_id, page_title, url and content to build the document.
        Override this method to provide a custom document builder.

        Args:
            document: Document object
            content: Plain text content
        Returns:
            tuple containing full document dictionary and simplified document dictionary
        """
        full_doc = {
            "id": getattr(document, "page_id", getattr(document, "id", "")),
            "title": getattr(document, "page_title", getattr(document, "title", "")),
            "text": content,
            "url": getattr(document, "url", None),
        }
        simplified_doc = {
            "id": full_doc["id"],
            "title": full_doc["title"],
            "text": content if len(content) < 200 else f"{content[:200]}...",
            "url": full_doc.get("url"),
        }
        return full_doc, simplified_doc
