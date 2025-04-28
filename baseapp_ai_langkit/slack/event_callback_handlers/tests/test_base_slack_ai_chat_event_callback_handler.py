from unittest.mock import MagicMock

from baseapp_ai_langkit.chats.models import ChatSession
from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChat
from baseapp_ai_langkit.slack.tests.factories import (
    SlackAIChatFactory,
    SlackEventFactory,
)
from baseapp_ai_langkit.slack.tests.test import SlackTestCase
from baseapp_ai_langkit.tests.factories import UserFactory


class SlackAIChatEventCallbackHandlerTestClass(BaseSlackAIChatEventCallbackHandler):
    def handle(self):
        pass


class TestBaseSlackAIChatEventCallbackHandler(SlackTestCase):
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

    def test_init(self):
        handler = SlackAIChatEventCallbackHandlerTestClass(
            slack_event_callback=self.mock_slack_event_callback
        )

        self.assertEqual(handler.slack_event_callback, self.mock_slack_event_callback)
        self.assertEqual(handler.slack_instance_controller, self.mock_slack_instance_controller)
        self.assertEqual(handler.data, self.slack_event.data)
        self.assertEqual(handler.team_id, self.slack_event.data["team_id"])
        self.assertEqual(handler.event_data, self.slack_event.data["event"])
        self.assertEqual(handler.event_type, self.slack_event.data["event"]["type"])
        self.assertIsNone(handler.slack_chat)

    def test_get_slack_chat(self):
        handler = SlackAIChatEventCallbackHandlerTestClass(
            slack_event_callback=self.mock_slack_event_callback
        )
        slack_chat = SlackAIChatFactory()
        handler.slack_chat = slack_chat

        self.assertEqual(handler.get_slack_chat(), slack_chat)

    def test_get_most_recent_slack_chat(self):
        handler = SlackAIChatEventCallbackHandlerTestClass(
            slack_event_callback=self.mock_slack_event_callback
        )

        team_id = "T12345"
        event_channel = "C12345"
        event_thread_ts = "1234567890.123456"

        matching_slack_event = SlackEventFactory(
            team_id=team_id,
            event_ts=event_thread_ts,
            event_type="message",
            data={
                "team_id": team_id,
                "event": {
                    "channel": event_channel,
                    "event_ts": event_thread_ts,
                },
            },
        )
        non_matching_slack_event = SlackEventFactory(
            team_id=team_id,
            event_ts="different_ts",
            event_type="message",
            data={
                "team_id": team_id,
                "event": {
                    "channel": "different_channel",
                    "event_ts": "different_ts",
                },
            },
        )

        matching_slack_chat = SlackAIChatFactory(slack_event=matching_slack_event)
        SlackAIChatFactory(slack_event=non_matching_slack_event)

        result = handler.get_most_recent_slack_chat(team_id, event_thread_ts, "message")

        self.assertEqual(result, matching_slack_chat)

    def test_get_most_recent_slack_chat_none(self):
        handler = SlackAIChatEventCallbackHandlerTestClass(
            slack_event_callback=self.mock_slack_event_callback
        )

        result = handler.get_most_recent_slack_chat("T12345", "1234567890.123456", "message")
        self.assertIsNone(result)

    def test_create_new_slack_chat(self):
        handler = SlackAIChatEventCallbackHandlerTestClass(
            slack_event_callback=self.mock_slack_event_callback
        )

        user = UserFactory()

        chat_session_count_before = ChatSession.objects.count()
        slack_chat_count_before = SlackAIChat.objects.count()

        handler.create_new_slack_chat(user=user)

        self.assertEqual(ChatSession.objects.count(), chat_session_count_before + 1)
        self.assertEqual(SlackAIChat.objects.count(), slack_chat_count_before + 1)

        created_chat_session = ChatSession.objects.latest("id")
        created_slack_chat = SlackAIChat.objects.latest("id")

        self.assertEqual(created_chat_session.user, user)
        self.assertEqual(created_slack_chat.chat_session, created_chat_session)
        self.assertEqual(created_slack_chat.slack_event, self.slack_event)
        self.assertEqual(handler.slack_chat, created_slack_chat)
