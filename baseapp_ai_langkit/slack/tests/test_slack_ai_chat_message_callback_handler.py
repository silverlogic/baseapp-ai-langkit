from unittest.mock import MagicMock, patch

from django.utils.translation import gettext_lazy as _

from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_message_callback_handler import (
    SlackAIChatMessageCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.tests.factories import UserFactory

from .factories import SlackAIChatFactory, SlackEventFactory
from .test import SlackTestCase


class TestSlackAIChatMessageCallbackHandler(SlackTestCase):
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
                    "channel_type": "channel",
                    "thread_ts": "1234567890.123456",
                    "event_ts": "1234567890.123456",
                },
            }
        )
        self.mock_slack_event_callback = MagicMock(spec=BaseSlackEventCallback)
        self.mock_slack_event_callback.slack_event = self.slack_event
        self.mock_slack_event_callback.data = self.slack_event.data
        self.mock_slack_event_callback.team_id = self.slack_event.data["team_id"]
        self.mock_slack_event_callback.event_data = self.slack_event.data["event"]
        self.mock_slack_event_callback.event_type = self.slack_event.data["event"]["type"]

        self.mock_slack_instance_controller = MagicMock()
        self.mock_slack_event_callback.slack_instance_controller = (
            self.mock_slack_instance_controller
        )

        self.handler = SlackAIChatMessageCallbackHandler(
            slack_event_callback=self.mock_slack_event_callback
        )
        self.handler.slack_instance_controller = self.mock_slack_instance_controller

    def test_handle_bot_message(self):
        self.handler.event_data = {
            "type": "message",
            "bot_id": "B12345",
            "channel_type": "channel",
            "thread_ts": "1234567890.123456",
        }

        with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
            self.handler.handle()

        self.assertIn("is_bot", str(context.exception))

    def test_handle_channel_message_without_thread(self):
        self.handler.event_data = {
            "type": "message",
            "channel_type": "channel",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
        }

        with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
            self.handler.handle()

        self.assertIn("is_in_thread", str(context.exception))

    def test_handle_channel_message_with_thread(self):
        matching_slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "channel": self.dummy_channel_id(),
                    "event_ts": "1234567890.123456",
                },
            }
        )
        slack_chat = SlackAIChatFactory(slack_event=matching_slack_event, celery_task_id=None)

        self.handler.event_data = {
            "type": "message",
            "channel_type": "channel",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "thread_ts": "1234567890.123456",
        }

        self.handler.handle()

        self.assertEqual(self.handler.slack_chat, slack_chat)

    def test_handle_im_message_with_thread(self):
        matching_slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "channel": self.dummy_channel_id(),
                    "event_ts": "1234567890.123456",
                },
            }
        )
        slack_chat = SlackAIChatFactory(slack_event=matching_slack_event, celery_task_id=None)

        self.handler.event_data = {
            "type": "message",
            "channel_type": "im",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "thread_ts": "1234567890.123456",
        }

        self.handler.handle()

        self.assertEqual(self.handler.slack_chat, slack_chat)

    def test_handle_im_message_without_thread(self):
        self.handler.event_data = {
            "type": "message",
            "channel_type": "im",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
        }

        user = UserFactory()
        self.mock_slack_instance_controller.get_or_create_user_from_slack_user.return_value = (
            user,
            True,
        )

        self.handler.handle()

        self.assertIsNotNone(self.handler.slack_chat)
        self.assertEqual(self.handler.slack_chat.chat_session.user, user)

    def test_handle_slack_chat_not_found(self):
        self.handler.get_most_recent_slack_chat = MagicMock(return_value=None)

        self.handler.event_data = {
            "type": "message",
            "channel_type": "channel",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "thread_ts": "1234567890.123456",
        }

        with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
            self.handler.handle()

        self.assertIn("slack_chat is None", str(context.exception))

    def test_handle_celery_task_processing(self):
        matching_slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "channel": self.dummy_channel_id(),
                    "event_ts": "1234567890.123456",
                },
            }
        )
        slack_chat = SlackAIChatFactory(slack_event=matching_slack_event)

        self.handler.get_most_recent_slack_chat = MagicMock(return_value=slack_chat)

        self.handler.event_data = {
            "type": "message",
            "channel_type": "channel",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "thread_ts": "1234567890.123456",
        }

        with self.settings(CELERY_TASK_ALWAYS_EAGER=False):
            with patch("baseapp_ai_langkit.slack.models.AsyncResult") as mock_async_result:
                mock_result = MagicMock()
                mock_result.ready.return_value = False
                mock_result.backend = MagicMock()
                mock_async_result.return_value = mock_result

                with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
                    self.handler.handle()

                self.mock_slack_instance_controller.slack_web_client.chat_postMessage.assert_called_once_with(
                    channel=self.dummy_channel_id(),
                    text=_("Please wait, still processing the previous message"),
                    thread_ts="1234567890.123456",
                )

                self.assertIn("is_celery_task_processing", str(context.exception))
