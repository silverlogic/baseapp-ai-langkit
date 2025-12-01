"""
Abstract fetch tool for MCP servers.

This tool provides a generic fetch interface that can be configured with
custom fetch and content processing functions.
"""

import logging
from typing import Any, Callable, Dict, Tuple

from baseapp_mcp import exceptions
from baseapp_mcp.tools.base_mcp_tool import MCPTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FetchArgs(BaseModel):
    id: str = Field(..., description="Numeric ID of the document to retrieve.")


class FetchTool(MCPTool):
    """
    Generic fetch tool that accepts fetch and content processing functions.

    The fetch function should accept a document ID and return a document object.
    The content_processor function should accept the document object and return
    plain text content.
    The doc_builder function should accept (document, content) and return
    (full_doc_dict, simplified_doc_dict).
    """

    name: str = "fetch"
    description: str = "Fetch a document by its unique ID."
    args_schema = FetchArgs

    def __init__(
        self,
        user_identifier: str,
        fetch_function: Callable[[str], Any] | None = None,
        content_processor: Callable[[Any], str] | None = None,
        doc_builder: Callable[[Any, str], Tuple[Dict[str, Any], Dict[str, Any]]] | None = None,
    ):
        """
        Initialize FetchTool with user identifier and optional functions.

        Args:
            user_identifier: Identifier for the user
            fetch_function: Optional function that takes a document ID and returns a document object
            content_processor: Optional function that takes a document and returns plain text content.
                              If not provided, assumes document has a 'html' attribute and uses strip_html_tags.
            doc_builder: Optional function that takes (document, content) and returns
                        (full_doc_dict, simplified_doc_dict). If not provided, uses default structure.
        """
        super().__init__(user_identifier)
        self._fetch_function = fetch_function
        self._content_processor = content_processor
        self._doc_builder = doc_builder

    def configure_fetch_function(self, fetch_function: Callable[[str], Any]):
        """Configure the fetch function to use."""
        self._fetch_function = fetch_function

    def configure_content_processor(self, content_processor: Callable[[Any], str]):
        """Configure the content processor function to use."""
        self._content_processor = content_processor

    def configure_doc_builder(
        self, doc_builder: Callable[[Any, str], Tuple[Dict[str, Any], Dict[str, Any]]]
    ):
        """Configure the document builder function to use."""
        self._doc_builder = doc_builder

    def tool_func_core(self, id: str) -> Dict[str, Any] | Tuple[Dict[str, Any], Dict[str, Any]]:
        if not id or not id.strip():
            raise exceptions.MCPValidationError("Document ID cannot be empty or whitespace.")

        if self._fetch_function is None:
            raise exceptions.MCPConfigurationError(
                "Fetch function not configured. Call configure_fetch_function() or "
                "provide fetch_function in __init__."
            )

        try:
            document = self._fetch_function(id.strip())
        except Exception as e:
            logger.error(f"Error fetching document {id}: {e}")
            raise exceptions.MCPDataError(f"Document with ID {id} not found.")

        # Process content
        if self._content_processor:
            content = self._content_processor(document)
        else:
            # Default: try to use strip_html_tags if available
            try:
                from baseapp_ai_langkit.embeddings.context_utils import strip_html_tags

                html_content = getattr(document, "html", None)
                if html_content:
                    content = strip_html_tags(html_content)
                else:
                    content = str(document)
            except ImportError:
                # Fallback if strip_html_tags not available
                content = getattr(document, "html", str(document))

        # Build document dict
        if self._doc_builder:
            full_doc, simplified_doc = self._doc_builder(document, content)
        else:
            # Default document structure
            full_doc = {
                "id": getattr(document, "page_id", getattr(document, "id", id)),
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
