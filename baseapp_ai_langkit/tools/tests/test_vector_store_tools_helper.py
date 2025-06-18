from typing import Type

from django.test import TestCase

from baseapp_ai_langkit.tools.models import InlineVectorStoreTool
from baseapp_ai_langkit.tools.vector_store_tools_helper import VectorStoreToolsHelper


class MockInlineVectorStoreTool(InlineVectorStoreTool):
    name = "MockInlineVectorStoreTool"
    description = "MockInlineVectorStoreTool description"


class MockAgentWithVectorStoreToolsHelper(VectorStoreToolsHelper):
    tools_list = [MockInlineVectorStoreTool]

    def get_vector_store_key(self, tool_class: Type[InlineVectorStoreTool]) -> str:
        return f"test_vector_store_{tool_class.__name__}"


class TestVectorStoreToolsHelper(TestCase):
    def test_get_new_vector_store(self):
        manager = MockAgentWithVectorStoreToolsHelper()
        vector_store, created = manager.get_vector_store(MockInlineVectorStoreTool)
        self.assertIsNotNone(vector_store)
        self.assertTrue(created)
        self.assertEqual(vector_store.name, "test_vector_store_MockInlineVectorStoreTool")

    def test_get_existing_vector_store(self):
        manager = MockAgentWithVectorStoreToolsHelper()
        manager.create_vector_store(InlineVectorStoreTool)
        vector_store, created = manager.get_vector_store(InlineVectorStoreTool)
        self.assertIsNotNone(vector_store)
        self.assertFalse(created)

    def test_agents_tools_manager_get_tools(self):
        manager = MockAgentWithVectorStoreToolsHelper()
        tools = manager.get_tools()
        self.assertEqual(len(tools), 1)
        self.assertIsInstance(tools[0], InlineVectorStoreTool)
