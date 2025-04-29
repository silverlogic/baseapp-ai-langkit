from unittest.mock import MagicMock, patch

from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_exception_handler import (
    SlackAIChatExceptionHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController
from baseapp_ai_langkit.slack.tests.factories import SlackEventFactory
from baseapp_ai_langkit.slack.tests.test import SlackTestCase


class TestSlackAIChatExceptionHandler(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "message",
                    "user": self.dummy_real_user_id(),
                    "channel": self.dummy_channel_id(),
                    "event_ts": "1234567890.123456",
                },
            }
        )

        self.handler = SlackAIChatExceptionHandler(
            slack_event_callback=self.create_mock_slack_event_callback(self.slack_event)
        )
        self.handler.verify_incoming_app = MagicMock()
        self.handler.verify_if_is_slack_chat_bot = MagicMock()

    def test_handle_exception_success(self):
        self.mock_slack_api_call("chat.postMessage")

        self.handler.handle()

        self.assert_slack_api_call(
            "chat.postMessage",
            expected_body={
                "channel": self.slack_event.data["event"]["channel"],
                "blocks": [],
                "text": "Error while processing your request. Please try again later or contact support.",
                "thread_ts": self.slack_event.data["event"]["event_ts"],
            },
        )

    def test_handle_exception_with_slack_api_error(self):
        self.mock_slack_api_call(
            "chat.postMessage",
            response_data={"ok": False, "error": "channel_not_found"},
            status=400,
        )

        with patch(
            "baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_exception_handler.logger"
        ) as mock_logger:
            self.handler.handle()

            mock_logger.exception.assert_called_once()
            log_message = mock_logger.exception.call_args[0][0]
            self.assertIn("Error while sending error message to slack", log_message)
            self.assertIn(self.slack_event.data["team_id"], log_message)

    def create_mock_slack_event_callback(self, slack_event):
        mock_slack_event_callback = MagicMock(spec=BaseSlackEventCallback)
        mock_slack_event_callback.slack_event = slack_event
        mock_slack_event_callback.data = slack_event.data
        mock_slack_event_callback.team_id = slack_event.data["team_id"]
        mock_slack_event_callback.event_data = slack_event.data["event"]
        mock_slack_event_callback.event_type = slack_event.data["event"]["type"]

        mock_slack_event_callback.slack_instance_controller = SlackInstanceController()
        return mock_slack_event_callback
