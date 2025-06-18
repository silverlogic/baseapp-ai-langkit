from typing import Type

from django.test import TestCase

from baseapp_ai_langkit.vector_stores.tools.inline_vector_store_tool import (
    InlineVectorStoreTool,
)
from baseapp_ai_langkit.vector_stores.tools.tools_with_vector_store_helper import (
    ToolsWithVectorStoreHelper,
)


class MockInlineVectorStoreTool(InlineVectorStoreTool):
    name = "MockInlineVectorStoreTool"
    description = "MockInlineVectorStoreTool description"


class MockAgentWithToolsWithVectorStoreHelper(ToolsWithVectorStoreHelper):
    tools_list = [MockInlineVectorStoreTool]

    def get_vector_store_key(self, tool_class: Type[InlineVectorStoreTool]) -> str:
        return f"test_vector_store_{tool_class.__name__}"


class TestToolsWithVectorStoreHelper(TestCase):
    def test_get_new_vector_store(self):
        manager = MockAgentWithToolsWithVectorStoreHelper()
        vector_store, created = manager.get_vector_store(MockInlineVectorStoreTool)
        self.assertIsNotNone(vector_store)
        self.assertTrue(created)
        self.assertEqual(vector_store.name, "test_vector_store_MockInlineVectorStoreTool")

    def test_get_existing_vector_store(self):
        manager = MockAgentWithToolsWithVectorStoreHelper()
        manager.create_vector_store(InlineVectorStoreTool)
        vector_store, created = manager.get_vector_store(InlineVectorStoreTool)
        self.assertIsNotNone(vector_store)
        self.assertFalse(created)

    def test_agents_tools_manager_get_tools(self):
        manager = MockAgentWithToolsWithVectorStoreHelper()
        tools = manager.get_tools()
        self.assertEqual(len(tools), 1)
        self.assertIsInstance(tools[0], InlineVectorStoreTool)
