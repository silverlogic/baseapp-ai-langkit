import uuid
from unittest.mock import MagicMock, patch

from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.slack_ai_chat_event_callback import (
    SlackAIChatEventCallback,
)

from .factories import SlackAIChatFactory, SlackEventFactory
from .test import SlackTestCase


class TestSlackAIChatEventCallback(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "message",
                    "text": "Hello AI assistant",
                    "user": self.dummy_real_user_id(),
                    "channel": self.dummy_channel_id(),
                },
            }
        )

    @patch("baseapp_ai_langkit.slack.tasks.slack_process_incoming_user_slack_message.apply_async")
    def test_apply_process_incoming_user_slack_message_task(self, mock_apply_async):
        callback = SlackAIChatEventCallback(self.slack_event.id)
        slack_chat = SlackAIChatFactory()

        mock_handler = MagicMock(spec=BaseSlackAIChatEventCallbackHandler)
        mock_handler.get_slack_chat.return_value = slack_chat
        mock_handler.get_event_text.return_value = "Hello AI assistant"

        mock_async_result = MagicMock()
        mock_async_result.id = uuid.uuid4()
        mock_apply_async.return_value = mock_async_result

        callback.apply_process_incoming_user_slack_message_task(handler=mock_handler)

        mock_handler.get_slack_chat.assert_called_once()
        mock_handler.get_event_text.assert_called_once()

        mock_apply_async.assert_called_once_with(
            kwargs=dict(
                slack_chat_id=slack_chat.id,
                slack_message_text="Hello AI assistant",
            )
        )

        self.assertEqual(slack_chat.celery_task_id, mock_async_result.id)
