from typing import Type

from django.test import TestCase

from baseapp_ai_langkit.base.agents.agents_tools_manager import AgentsToolsManager
from baseapp_ai_langkit.tools.models import InlineTool


class MockInlineTool(InlineTool):
    name = "MockInlineTool"
    description = "MockInlineTool description"


class MockAgentsToolsManager(AgentsToolsManager):
    tools_list = [MockInlineTool]

    def get_vector_store_key(self, tool_class: Type[InlineTool]) -> str:
        return f"test_vector_store_{tool_class.__name__}"


class TestAgentsToolsManager(TestCase):
    def test_get_new_vector_store(self):
        manager = MockAgentsToolsManager()
        vector_store, created = manager.get_vector_store(MockInlineTool)
        self.assertIsNotNone(vector_store)
        self.assertTrue(created)
        self.assertEqual(vector_store.name, "test_vector_store_MockInlineTool")

    def test_get_existing_vector_store(self):
        manager = MockAgentsToolsManager()
        manager.create_vector_store(MockInlineTool)
        vector_store, created = manager.get_vector_store(MockInlineTool)
        self.assertIsNotNone(vector_store)
        self.assertFalse(created)

    def test_agents_tools_manager_get_tools(self):
        manager = MockAgentsToolsManager()
        tools = manager.get_tools()
        self.assertEqual(len(tools), 1)
        self.assertIsInstance(tools[0], InlineTool)
