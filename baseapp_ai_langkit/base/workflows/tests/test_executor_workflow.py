from unittest.mock import MagicMock

from django.test import TestCase

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.workflows.executor_workflow import ExecutorWorkflow


class MockNode(MagicMock):
    def invoke(self, *args, **kwargs):
        return MagicMock(content="Mocked content")


class MockWorkflowChain(MagicMock):
    def invoke(self, *args, **kwargs):
        return {"output": "Mocked content"}


class TestExecutorWorkflow(TestCase):
    def setUp(self):
        self.nodes = {
            "node1": MockNode(spec=LLMNodeInterface),
            "node2": MockNode(spec=LLMNodeInterface),
        }
        self.config = {}
        self.workflow = ExecutorWorkflow(nodes=self.nodes, config=self.config)
        self.workflow.workflow_chain = MockWorkflowChain()

    def test_executor_workflow_initialization(self):
        self.assertEqual(self.workflow.nodes, self.nodes)
        self.assertIsInstance(self.workflow.state_graph_schema, type)
        self.assertEqual(len(self.workflow.workflow.nodes), 2)
        self.assertIn("node1", self.workflow.workflow.nodes)
        self.assertIn("node2", self.workflow.workflow.nodes)

    def test_executor_workflow_execution(self):
        result = self.workflow.execute()
        self.assertEqual(result["output"], "Mocked content")
