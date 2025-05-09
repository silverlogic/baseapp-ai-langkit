from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage, AnyMessage

from baseapp_ai_langkit.base.workers.synthesizer_worker import SynthesizerWorker


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test synthesized response")


class TestSynthesizerWorker(TestCase):
    def setUp(self):
        self.worker = SynthesizerWorker(
            llm=MockLLM(spec=FakeChatModel),
            config={},
        )

    def test_synthesizer_worker_initialization(self):
        self.assertIsNotNone(self.worker.llm)
        self.assertEqual(self.worker.config, {})
        self.assertEqual(len(self.worker.state_modifier_schema), 2)

    def test_synthesizer_worker_state_modifiers(self):
        # Test first schema
        first_schema = self.worker.state_modifier_schema[0]
        self.assertIn("user_prompt", first_schema.required_placeholders)
        self.assertIn("synthesizer_context", first_schema.required_placeholders)

        # Test second schema
        second_schema = self.worker.state_modifier_schema[1]
        self.assertIn("selected_nodes_list", second_schema.required_placeholders)

    def test_synthesizer_worker_invoke(self):
        messages = [MagicMock(spec=AnyMessage)]
        state = {
            "user_prompt": "test prompt",
            "synthesizer_context": "test context",
            "selected_nodes_list": "node1, node2",
        }

        response = self.worker.invoke(messages, state)

        self.assertIsInstance(response, AIMessage)
        self.assertEqual(response.content, "Test synthesized response")

    def test_synthesizer_worker_invoke_without_nodes(self):
        messages = [MagicMock(spec=AnyMessage)]
        state = {"user_prompt": "test prompt", "synthesizer_context": "test context"}

        response = self.worker.invoke(messages, state)

        self.assertIsInstance(response, AIMessage)
        self.assertEqual(response.content, "Test synthesized response")

    def test_synthesizer_worker_invoke_with_empty_nodes(self):
        messages = [MagicMock(spec=AnyMessage)]
        state = {
            "user_prompt": "test prompt",
            "synthesizer_context": "test context",
            "selected_nodes_list": [],
        }

        response = self.worker.invoke(messages, state)

        self.assertIsInstance(response, AIMessage)
        self.assertEqual(response.content, "Test synthesized response")
