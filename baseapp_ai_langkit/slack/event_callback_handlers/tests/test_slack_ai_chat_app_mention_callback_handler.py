from unittest.mock import MagicMock

from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_app_mention_callback_handler import (
    SlackAIChatAppMentionCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.tests.factories import SlackEventFactory
from baseapp_ai_langkit.slack.tests.test import SlackTestCase
from baseapp_ai_langkit.tests.factories import UserFactory


class TestSlackAIChatAppMentionCallbackHandler(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "app_mention",
                    "text": "<@U12345> Hello AI assistant",
                    "user": self.dummy_real_user_id(),
                    "channel": self.dummy_channel_id(),
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

        self.handler = SlackAIChatAppMentionCallbackHandler(
            slack_event_callback=self.mock_slack_event_callback
        )
        self.handler.slack_instance_controller = self.mock_slack_instance_controller
        self.handler.verify_incoming_app = MagicMock()
        self.handler.verify_if_is_slack_chat_bot = MagicMock()

    def test_handle_app_mention_in_thread(self):
        self.handler.event_data = {
            "type": "app_mention",
            "text": "<@U12345> Hello AI assistant",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "thread_ts": "1234567890.123456",
        }

        with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
            self.handler.handle()

        self.assertIn("is_in_thread", str(context.exception))

    def test_handle_app_mention_not_in_thread(self):
        self.handler.event_data = {
            "type": "app_mention",
            "text": "<@U12345> Hello AI assistant",
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
        self.mock_slack_instance_controller.get_or_create_user_from_slack_user.assert_called_once_with(
            slack_user_id=self.dummy_real_user_id()
        )

    def test_handle_app_mention_from_bot_message(self):
        self.handler.event_data = {
            "type": "app_mention",
            "text": "<@U12345> Hello AI assistant",
            "user": self.dummy_real_user_id(),
            "channel": self.dummy_channel_id(),
            "bot_id": self.dummy_bot_user_id(),
            "subtype": "bot_message",
        }

        user = UserFactory()
        self.mock_slack_instance_controller.get_or_create_user_from_slack_bot.return_value = (
            user,
            True,
        )

        self.handler.handle()

        self.assertIsNotNone(self.handler.slack_chat)
        self.assertEqual(self.handler.slack_chat.chat_session.user, user)
        self.mock_slack_instance_controller.get_or_create_user_from_slack_bot.assert_called_once_with(
            bot_id=self.dummy_bot_user_id()
        )
