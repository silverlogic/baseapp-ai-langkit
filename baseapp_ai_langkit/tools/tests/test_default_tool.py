from django.test import TestCase

from baseapp_ai_langkit.tools.models import DefaultTool
from baseapp_ai_langkit.vector_stores.tests.factories import DefaultVectorStoreFactory


class TestDefaultTool(TestCase):
    def setUp(self):
        self.vector_store = DefaultVectorStoreFactory()
        self.tool = DefaultTool(
            name="Test Tool", description="A test tool", vector_store=self.vector_store
        )

    def test_initialization(self):
        self.assertEqual(self.tool.name, "Test Tool")
        self.assertEqual(self.tool.description, "A test tool")
        self.assertEqual(self.tool.vector_store, self.vector_store)

    def test_to_langchain_tool(self):
        langchain_tool = self.tool.to_langchain_tool()
        self.assertEqual(langchain_tool.name, "Test Tool")
        self.assertEqual(langchain_tool.description, "A test tool")
