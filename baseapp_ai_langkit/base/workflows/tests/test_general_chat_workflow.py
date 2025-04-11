from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow


class MockWorkflowChain(MagicMock):
    def invoke(self, *args, **kwargs):
        return {"messages": [AIMessage(content="Test response")]}


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test response")


class TestGeneralChatWorkflow(TestCase):
    def setUp(self):
        self.llm = MockLLM(spec=FakeChatModel)
        self.checkpointer = MagicMock()
        self.config = {}

        self.workflow = GeneralChatWorkflow(
            llm=self.llm,
            checkpointer=self.checkpointer,
            config=self.config,
            max_messages=3,
            retained_messages=1,
        )
        self.workflow.workflow_chain = MockWorkflowChain()

    def test_general_chat_workflow_initialization(self):
        self.assertEqual(self.workflow.llm, self.llm)
        self.assertEqual(self.workflow.checkpointer, self.checkpointer)
        self.assertEqual(self.workflow.max_messages, 3)
        self.assertEqual(self.workflow.retained_messages, 1)
        self.assertEqual(self.workflow.config, self.config)

    def test_workflow_node_general_llm(self):
        state = {"messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there")]}

        result = self.workflow.workflow_node_general_llm(state)

        self.assertIn("messages", result)
        self.assertEqual(len(result["messages"]), 3)  # Original messages + new response
        self.assertEqual(result["messages"][-1].content, "Test response")

    def test_execute_workflow(self):
        result = self.workflow.execute("Test prompt")

        self.assertIsInstance(result, dict)
        self.assertIn("messages", result)
        self.assertEqual(result["messages"][0].content, "Test response")

    def test_execute_workflow_with_error(self):
        self.workflow.error = Exception("Test error")

        with self.assertRaises(Exception):
            self.workflow.execute("Test prompt")

    def test_workflow_node_general_llm_with_error(self):
        self.llm.invoke = MagicMock(side_effect=Exception("Test error"))

        state = {"messages": [HumanMessage(content="Hello")]}

        result = self.workflow.workflow_node_general_llm(state)

        self.assertIn("messages", result)
        self.assertEqual(len(result["messages"]), 1)
        self.assertEqual(result["messages"][-1].content, "Hello")
