from unittest.mock import patch

import pytest
from langchain.tools import Tool

from baseapp_ai_langkit.tools.tests.factories import DefaultToolFactory

pytestmark = pytest.mark.django_db


def test_default_tool_to_langchain_tool():
    tool = DefaultToolFactory(name="Test Tool", description="A test description")
    langchain_tool = tool.to_langchain_tool()

    assert isinstance(langchain_tool, Tool)
    assert langchain_tool.name == "Test Tool"
    assert langchain_tool.description == "A test description"

    assert langchain_tool.func == tool.tool_func


def test_default_tool_tool_func():
    tool = DefaultToolFactory()

    with patch.object(
        tool.vector_store,
        "similarity_search",
        return_value=[{"content": "Doc1"}, {"content": "Doc2"}],
    ) as mock_similarity_search:
        result = tool.tool_func("query")
        mock_similarity_search.assert_called_once_with("query")
        assert result == "Doc1\nDoc2"
