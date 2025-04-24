from unittest.mock import patch

from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackEvent
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

from .factories import SlackEventFactory
from .test import SlackTestCase


class TestBaseSlackEventCallback(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "message",
                    "text": "Hello world",
                    "user": self.dummy_real_user_id(),
                    "channel": self.dummy_channel_id(),
                },
            }
        )

    def test_init(self):
        callback = BaseSlackEventCallback(self.slack_event.id)
        self.assertEqual(callback.slack_event, self.slack_event)
        self.assertIsInstance(callback.slack_instance_controller, SlackInstanceController)

    @patch.object(BaseSlackEventCallback, "handle_message")
    def test_call_success(self, mock_handle_message):
        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        mock_handle_message.assert_called_once()
        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success)

    @patch.object(BaseSlackEventCallback, "handle_message")
    def test_call_warning(self, mock_handle_message):
        mock_handle_message.side_effect = BaseSlackEventCallback.WarningException("Test warning")

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    @patch.object(BaseSlackEventCallback, "handle_message")
    def test_call_exception(self, mock_handle_message):
        mock_handle_message.side_effect = Exception("Test exception")

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.failed)

    def test_unsupported_event_type(self):
        self.slack_event.data["event"]["type"] = "unsupported_type"
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.failed)

    def test_handle_tokens_revoked(self):
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {"type": "tokens_revoked", "tokens": {"bot": ["xoxb-12345"]}},
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    def test_handle_app_uninstalled(self):
        self.slack_event.data = {"team_id": "T12345", "event": {"type": "app_uninstalled"}}
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    def test_handle_app_mention(self):
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {
                "type": "app_mention",
                "user": self.dummy_real_user_id(),
                "channel": self.dummy_channel_id(),
                "text": "<@U12345> hello",
            },
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    def test_handle_reaction_added(self):
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {
                "type": "reaction_added",
                "user": self.dummy_real_user_id(),
                "reaction": "thumbsup",
            },
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    def test_handle_reaction_removed(self):
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {
                "type": "reaction_removed",
                "user": self.dummy_real_user_id(),
                "reaction": "thumbsup",
            },
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)

    def test_handle_link_shared(self):
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {
                "type": "link_shared",
                "user": self.dummy_real_user_id(),
                "channel": self.dummy_channel_id(),
                "links": [{"url": "https://example.com"}],
            },
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(self.slack_event.status, SlackEvent.STATUS.success_with_warnings)
