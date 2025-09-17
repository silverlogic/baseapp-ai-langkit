from unittest.mock import patch

from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackEventStatus
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController
from baseapp_ai_langkit.slack.tests.factories import (
    SlackEventFactory,
    SlackEventStatusFactory,
)
from baseapp_ai_langkit.slack.tests.test import SlackTestCase


class TestBaseSlackEventCallback(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event_data = {
            "team_id": "T12345",
            "event": {
                "type": "message",
                "text": "Hello world",
                "user": self.dummy_real_user_id(),
                "channel": self.dummy_channel_id(),
            },
        }
        self.slack_event = SlackEventFactory(
            team_id="T12345", event_type="message", data=self.slack_event_data
        )
        self.slack_event_status = SlackEventStatusFactory(
            slack_event=self.slack_event, status=SlackEventStatus.STATUS.pending
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
        self.assertEqual(
            self.slack_event.event_statuses.last().status, SlackEventStatus.STATUS.success
        )

    @patch.object(BaseSlackEventCallback, "handle_message")
    def test_call_warning(self, mock_handle_message):
        mock_handle_message.side_effect = BaseSlackEventCallback.WarningException("Test warning")

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )

    @patch.object(BaseSlackEventCallback, "handle_message")
    def test_call_exception(self, mock_handle_message):
        mock_handle_message.side_effect = Exception("Test exception")

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.assertEqual(
            self.slack_event.event_statuses.last().status, SlackEventStatus.STATUS.failed
        )

    def test_unsupported_event_type(self):
        slack_event = SlackEventFactory(
            team_id="T12345",
            event_type="unsupported_type",
            data={
                "team_id": "T12345",
                "event": {"type": "unsupported_type"},
            },
        )
        SlackEventStatusFactory(slack_event=slack_event, status=SlackEventStatus.STATUS.pending)
        callback = BaseSlackEventCallback(slack_event.id)
        callback()

        slack_event.refresh_from_db()
        self.assertEqual(slack_event.event_statuses.last().status, SlackEventStatus.STATUS.failed)
        self.assertEqual(
            slack_event.event_statuses.last().status_message,
            "Unable to handle event_type: unsupported_type",
        )

    def test_handle_tokens_revoked(self):
        self.slack_event.event_type = "tokens_revoked"
        self.slack_event.data = {
            "team_id": "T12345",
            "event": {"type": "tokens_revoked", "tokens": {"bot": ["xoxb-12345"]}},
        }
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.slack_event.refresh_from_db()
        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event tokens_revoked for bot_user_ids: ['xoxb-12345']",
        )

    def test_handle_app_uninstalled(self):
        self.slack_event.event_type = "app_uninstalled"
        self.slack_event.data = {"team_id": "T12345", "event": {"type": "app_uninstalled"}}
        self.slack_event.save()

        callback = BaseSlackEventCallback(self.slack_event.id)
        callback()

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event app_uninstalled for team_id: T12345",
        )

    def test_handle_app_mention(self):
        self.slack_event.event_type = "app_mention"
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

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event app_mention for team_id: T12345",
        )

    def test_handle_reaction_added(self):
        self.slack_event.event_type = "reaction_added"
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

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event reaction_added for team_id: T12345",
        )

    def test_handle_reaction_removed(self):
        self.slack_event.event_type = "reaction_removed"
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

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event reaction_removed for team_id: T12345",
        )

    def test_handle_link_shared(self):
        self.slack_event.event_type = "link_shared"
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

        self.assertEqual(
            self.slack_event.event_statuses.last().status,
            SlackEventStatus.STATUS.success_with_warnings,
        )
        self.assertEqual(
            self.slack_event.event_statuses.last().status_message,
            "Event link_shared for team_id: T12345",
        )
