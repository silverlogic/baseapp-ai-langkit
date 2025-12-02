from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workers.orchestrator_worker import (
    AvailableNode,
    OrchestratorWorker,
)
from baseapp_ai_langkit.base.workers.synthesizer_worker import SynthesizerWorker
from baseapp_ai_langkit.base.workflows.orchestrated_conversational_workflow import (
    OrchestratedConversationalWorkflow,
)


class MockWorkflowChain(MagicMock):
    def invoke(self, *args, **kwargs):
        return {"messages": [AIMessage(content="Test response")]}


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test summary")


class MockOrchestratorAgent(MagicMock):
    def invoke(self, *args, **kwargs):
        return MagicMock(
            nodes=[AvailableNode(name="test_node", prompt="test prompt")],
            synthesizer_context="test context",
        )


class MockSynthesizerWorker(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Synthesized response")


class MockNode(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Node response")


class TestOrchestratedConversationalWorkflow(TestCase):
    def setUp(self):
        self.llm = MockLLM(spec=FakeChatModel)
        self.checkpointer = MagicMock()
        self.orchestrator = MockOrchestratorAgent(spec=OrchestratorWorker)
        self.synthesizer = MockSynthesizerWorker(spec=SynthesizerWorker)
        self.config = {}

        self.nodes = {
            "test_node": {
                "description": "Test node description",
                "node": MessagesWorker(
                    llm=self.llm,
                    config={},
                ),
            }
        }

        self.workflow = OrchestratedConversationalWorkflow(
            llm=self.llm,
            checkpointer=self.checkpointer,
            nodes=self.nodes,
            orchestrator=self.orchestrator,
            synthesizer=self.synthesizer,
            config=self.config,
            max_messages=3,
            retained_messages=1,
        )
        self.workflow.workflow_chain = MockWorkflowChain()

    def test_orchestrated_workflow_initialization(self):
        self.assertEqual(self.workflow.llm, self.llm)
        self.assertEqual(self.workflow.checkpointer, self.checkpointer)
        self.assertEqual(self.workflow.nodes, self.nodes)
        self.assertEqual(self.workflow.orchestrator, self.orchestrator)
        self.assertEqual(self.workflow.synthesizer, self.synthesizer)
        self.assertEqual(self.workflow.max_messages, 3)
        self.assertEqual(self.workflow.retained_messages, 1)
        self.assertEqual(self.workflow.config, self.config)

    def test_workflow_node_orchestration(self):
        state = {"messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there")]}

        result = self.workflow.workflow_node_orchestration(state)

        self.assertIn("messages", result)
        self.assertIn("selected_nodes", result)
        self.assertIn("synthesizer_context", result)
        self.assertEqual(len(result["selected_nodes"]), 1)
        self.assertEqual(result["selected_nodes"][0].name, "test_node")
        self.assertEqual(result["synthesizer_context"], "test context")

    def test_workflow_node_call_node(self):
        state = {"node_key": "test_node", "custom_prompt": "test prompt"}

        result = self.workflow.workflow_node_call_node(state)

        self.assertIn("completed_nodes", result)
        self.assertEqual(len(result["completed_nodes"]), 1)
        self.assertIn("test_node response:", result["completed_nodes"][0])

    def test_workflow_node_synthesis(self):
        state = {
            "messages": [HumanMessage(content="Test prompt")],
            "selected_nodes": [AvailableNode(name="test_node", prompt="test prompt")],
            "completed_nodes": ["test_node response: Node output"],
            "synthesizer_context": "test context",
        }

        result = self.workflow.workflow_node_synthesis(state)

        self.assertIn("messages", result)
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][-1].content, "Synthesized response")
        self.assertEqual(result["selected_nodes"], [])
        self.assertEqual(result["completed_nodes"], [])

    def test_workflow_conditional_edge_assign_nodes_with_nodes(self):
        state = {"selected_nodes": [AvailableNode(name="test_node", prompt="test prompt")]}

        result = self.workflow.workflow_conditional_edge_assign_nodes(state)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].node, "test_node")

    def test_workflow_conditional_edge_assign_nodes_without_nodes(self):
        state = {"selected_nodes": []}

        result = self.workflow.workflow_conditional_edge_assign_nodes(state)

        self.assertEqual(result, "synthesis")

    def test_execute_workflow(self):
        result = self.workflow.execute("Test prompt")

        self.assertIsInstance(result, dict)
        self.assertIn("messages", result)

    def test_execute_workflow_with_error(self):
        self.workflow.error = Exception("Test error")

        with self.assertRaises(Exception):
            self.workflow.execute("Test prompt")

    def test_workflow_node_orchestration_with_error(self):
        state = {"messages": [HumanMessage(content="Test prompt")]}
        self.orchestrator.invoke = MagicMock(side_effect=Exception("Test orchestrator error"))

        result = self.workflow.workflow_node_orchestration(state)

        self.assertEqual(result, state)
        self.assertEqual(self.workflow.error.__str__(), "Test orchestrator error")

    def test_workflow_node_synthesis_with_error(self):
        state = {
            "messages": [HumanMessage(content="Test prompt")],
            "selected_nodes": [AvailableNode(name="test_node", prompt="test prompt")],
            "completed_nodes": ["test_node response: Node output"],
            "synthesizer_context": "test context",
        }
        self.synthesizer.invoke = MagicMock(side_effect=Exception("Test synthesizer error"))

        result = self.workflow.workflow_node_synthesis(state)

        self.assertEqual(result, state)
        self.assertEqual(self.workflow.error.__str__(), "Test synthesizer error")
