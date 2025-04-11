from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START

from baseapp_ai_langkit.base.workflows.conversational_workflow import (
    ConversationalWorkflow,
    ConversationState,
)


class MockConversationalWorkflow(ConversationalWorkflow):
    def workflow_node_general_llm(self, state: ConversationState):
        msg = self.llm.invoke(state["messages"])
        return {"messages": state["messages"] + [msg]}

    def setup_workflow_chain(self):
        self.workflow.add_node("general_llm", self.workflow_node_general_llm)
        self.add_memory_summarization_nodes()

        self.workflow.add_edge(START, "general_llm")
        self.add_memory_summarization_edges("general_llm", END)

        super().setup_workflow_chain()


class MockWorkflowChain(MagicMock):
    def invoke(self, *args, **kwargs):
        return {"messages": [AIMessage(content="Test response")]}


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test summary")


class TestConversationalWorkflow(TestCase):
    def setUp(self):
        self.llm = MockLLM(spec=FakeChatModel)
        self.checkpointer = MagicMock()
        self.config = {}

        self.workflow = MockConversationalWorkflow(
            llm=self.llm,
            checkpointer=self.checkpointer,
            config=self.config,
            max_messages=3,
            retained_messages=1,
        )
        self.workflow.workflow_chain = MockWorkflowChain()

    def test_conversational_workflow_initialization(self):
        self.assertEqual(self.workflow.llm, self.llm)
        self.assertEqual(self.workflow.checkpointer, self.checkpointer)
        self.assertEqual(self.workflow.max_messages, 3)
        self.assertEqual(self.workflow.retained_messages, 1)
        self.assertEqual(self.workflow.config, self.config)

    def test_workflow_node_summarize_conversation(self):
        state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there"),
                HumanMessage(content="How are you?"),
            ],
            "summary": "Previous conversation",
        }

        result = self.workflow.workflow_node_summarize_conversation(state)

        self.assertIn("summary", result)
        self.assertEqual(result["summary"], "Test summary")
        self.assertEqual(len(result["messages"]), 5)  # Remove messages + summary + retained message

    def test_workflow_node_maybe_rollback_memory_with_error(self):
        self.workflow.error = Exception("Test error")
        state = {"messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there")]}

        result = self.workflow.workflow_node_maybe_rollback_memory(state)

        self.assertEqual(len(result["messages"]), 3)  # Original messages + remove message

    def test_workflow_node_maybe_rollback_memory_without_error(self):
        state = {"messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there")]}

        result = self.workflow.workflow_node_maybe_rollback_memory(state)

        self.assertEqual(len(result["messages"]), 2)  # Original messages unchanged

    def test_execute_workflow(self):
        result = self.workflow.execute("Test prompt")

        self.assertIsInstance(result, dict)
        self.assertIn("messages", result)

    def test_execute_workflow_with_error(self):
        self.workflow.error = Exception("Test error")

        with self.assertRaises(Exception):
            self.workflow.execute("Test prompt")
