from unittest.mock import MagicMock

from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import AIMessage, AnyMessage

from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker


class MockLLM(MagicMock):
    def invoke(self, *args, **kwargs):
        return AIMessage(content="Test response")


class TestMessagesWorker(TestCase):
    def setUp(self):
        self.worker = MessagesWorker(
            llm=MockLLM(spec=FakeChatModel),
            config={},
        )

    def test_messages_worker_initialization(self):
        self.assertIsNotNone(self.worker.llm)
        self.assertEqual(self.worker.config, {})

    def test_messages_worker_invoke(self):
        messages = [MagicMock(spec=AnyMessage)]
        state = {"test_key": "test_value"}

        response = self.worker.invoke(messages, state)

        self.assertIsInstance(response, AIMessage)
        self.assertEqual(response.content, "Test response")

    def test_messages_worker_state_update(self):
        messages = [MagicMock(spec=AnyMessage)]
        state = {"test_key": "test_value"}

        self.worker.invoke(messages, state)

        state_modifiers = self.worker.get_state_modifier_list()
        for modifier in state_modifiers:
            self.assertIn("test_key", modifier.placeholders_data)
            self.assertEqual(modifier.placeholders_data["test_key"], "test_value")
