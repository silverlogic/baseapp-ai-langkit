from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow


class MockWorkflowChain(MagicMock):
    def invoke(self, *args, **kwargs):
        return {"messages": [AIMessage(content="Test response")]}


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test response")


class MockNode(MagicMock):
    def invoke(self, *args, **kwargs):
        return MagicMock(content="Mocked content")


class TestGeneralChatWorkflow(TestCase):
    def setUp(self):
        self.llm = MockLLM(spec=FakeChatModel)
        self.checkpointer = MagicMock()
        self.config = {}
        self.nodes = {
            "node1": MockNode(spec=LLMNodeInterface),
            "node2": MockNode(spec=LLMNodeInterface),
        }

        self.workflow = GeneralChatWorkflow(
            llm=self.llm,
            checkpointer=self.checkpointer,
            nodes=self.nodes,
            config=self.config,
            max_messages=3,
            retained_messages=1,
        )
        self.workflow.workflow_chain = MockWorkflowChain()

    def test_general_chat_workflow_initialization(self):
        self.assertEqual(self.workflow.llm, self.llm)
        self.assertEqual(self.workflow.nodes, self.nodes)
        self.assertEqual(self.workflow.checkpointer, self.checkpointer)
        self.assertEqual(self.workflow.max_messages, 3)
        self.assertEqual(self.workflow.retained_messages, 1)
        self.assertEqual(self.workflow.config, self.config)

    def test_execute_workflow(self):
        result = self.workflow.execute("Test prompt")

        self.assertIsInstance(result, dict)
        self.assertIn("messages", result)
        self.assertEqual(result["messages"][0].content, "Test response")

    def test_execute_workflow_with_error(self):
        self.workflow.error = Exception("Test error")

        with self.assertRaises(Exception):
            self.workflow.execute("Test prompt")
