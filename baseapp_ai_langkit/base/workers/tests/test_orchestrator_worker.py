from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AnyMessage

from baseapp_ai_langkit.base.workers.orchestrator_worker import (
    OrchestratorResponse,
    OrchestratorWorker,
)


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return OrchestratorResponse(nodes=[], synthesizer_context="").model_dump()


class TestOrchestratorWorker(TestCase):
    def setUp(self):
        self.available_nodes_list = [("node1", "prompt1"), ("node2", "prompt2")]
        self.worker = OrchestratorWorker(
            available_nodes_list=self.available_nodes_list,
            llm=MockLLM(spec=FakeChatModel),
            config={},
        )

    def test_orchestrator_worker_initialization(self):
        self.assertIn(
            "node1", self.worker.state_modifier_schema.placeholders_data["available_nodes_list"]
        )
        self.assertIn(
            "node2", self.worker.state_modifier_schema.placeholders_data["available_nodes_list"]
        )

    def test_orchestrator_response_structure(self):
        messages = [MagicMock(spec=AnyMessage)]
        response = self.worker.invoke(messages)
        self.assertIsInstance(response, dict)
        self.assertIn("nodes", response)
        self.assertIn("synthesizer_context", response)
