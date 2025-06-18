from django.test import TestCase

from baseapp_ai_langkit.base.tools.inline_tool import InlineTool


class MockedInlineTool(InlineTool):
    name = "Test Inline Tool"
    description = "A test inline tool"


class TestInlineTool(TestCase):
    def test_initialization(self):
        tool = MockedInlineTool()
        self.assertEqual(tool.name, "Test Inline Tool")
        self.assertEqual(tool.description, "A test inline tool")

    def test_initialization_with_args(self):
        tool = MockedInlineTool(name="Test Tool", description="A test tool")
        self.assertEqual(tool.name, "Test Tool")
        self.assertEqual(tool.description, "A test tool")

    def test_to_langchain_tool(self):
        tool = MockedInlineTool()
        langchain_tool = tool.to_langchain_tool()
        self.assertEqual(langchain_tool.name, "Test Inline Tool")
        self.assertEqual(langchain_tool.description, "A test inline tool")
