from unittest.mock import MagicMock, patch

from baseapp_ai_langkit.slack.base.interfaces.slack_chat_runner import (
    BaseSlackChatInterface,
)
from baseapp_ai_langkit.slack.models import SlackAIChatMessage, SlackEvent
from baseapp_ai_langkit.slack.slack_ai_chat_controller import SlackAIChatController

from .factories import SlackAIChatFactory, SlackEventFactory
from .test import SlackTestCase


class TestSlackAIChatController(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_message_text = "Hello AI assistant"
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "message",
                    "text": self.slack_message_text,
                    "user": self.dummy_real_user_id(),
                    "channel": self.dummy_channel_id(),
                    "channel_type": "channel",
                    "thread_ts": "1234567890.123456",
                    "event_ts": "1234567890.123456",
                },
            }
        )
        self.slack_chat = SlackAIChatFactory(slack_event=self.slack_event)
        self.controller = SlackAIChatController(
            slack_chat=self.slack_chat, user_message_slack_event=self.slack_event
        )

    def test_get_runner_class(self):
        runner = self.controller.get_runner_class()
        self.assertTrue(issubclass(runner, BaseSlackChatInterface))

    def test_collect_slack_context(self):
        self.mock_slack_api_call("conversations.info", response_data=self.conversations_info_data())

        context = self.controller.collect_slack_context()

        self.assertEqual(context["channel_name"], "Slack Channel: pytest")
        self.assertEqual(context["current_user"], self.slack_chat.chat_session.user.email)

    def test_collect_slack_context_api_error(self):
        self.mock_slack_api_call("conversations.info", response_data={}, status=400)

        with patch("baseapp_ai_langkit.slack.slack_ai_chat_controller.logging") as mock_logging:
            context = self.controller.collect_slack_context()

            self.assertEqual(context, {})
            mock_logging.exception.assert_called_once()

    def test_get_formatted_message_short_text(self):
        llm_output = "I am an AI assistant"

        formatted_chunks = self.controller.get_formatted_message(llm_output)

        self.assertEqual(len(formatted_chunks), 1)
        text, blocks = formatted_chunks[0]
        self.assertEqual(text, llm_output)
        self.assertEqual(
            blocks, [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}]
        )

    def test_get_formatted_message_long_text(self):
        long_text = "A" * 4000

        formatted_chunks = self.controller.get_formatted_message(long_text)

        self.assertEqual(len(formatted_chunks), 2)

        # First chunk should be 3000 chars with ellipsis
        text1, blocks1 = formatted_chunks[0]
        self.assertEqual(len(text1), 3000)
        self.assertTrue(text1.endswith("..."))
        self.assertEqual(blocks1, [{"type": "section", "text": {"type": "mrkdwn", "text": text1}}])

        # Second chunk should be the remainder
        text2, blocks2 = formatted_chunks[1]
        self.assertEqual(text2, long_text[2997:])  # 2997 = 3000 - len("...")
        self.assertEqual(blocks2, [{"type": "section", "text": {"type": "mrkdwn", "text": text2}}])

    def test_get_formatted_message_non_string_input(self):
        with self.assertRaises(ValueError):
            self.controller.get_formatted_message(123)

    def test_process_message_response(self):
        llm_output = "I am an AI assistant"
        formatted_chunks = [
            (llm_output, [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}])
        ]

        self.mock_slack_api_call(
            "chat.postMessage",
            response_data={"ok": True, "message": {"ts": "1234567890.654321", "type": "message"}},
        )

        self.controller.process_message_response(formatted_chunks)

        self.assert_slack_api_call(
            "chat.postMessage",
            expected_body={
                "channel": self.slack_event.data["event"]["channel"],
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}],
                "text": llm_output,
                "thread_ts": self.slack_event.data["event"]["event_ts"],
            },
        )

    def test_process_message_response_creates_models(self):
        llm_output = "I am an AI assistant"
        formatted_chunks = [
            (llm_output, [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}])
        ]

        self.mock_slack_api_call(
            "chat.postMessage",
            response_data={"ok": True, "message": {"ts": "1234567890.654321", "type": "message"}},
        )

        initial_slack_event_count = SlackEvent.objects.count()
        initial_slack_chat_message_count = SlackAIChatMessage.objects.count()

        self.controller.process_message_response(formatted_chunks)

        self.assertEqual(SlackEvent.objects.count(), initial_slack_event_count + 1)
        new_slack_event = SlackEvent.objects.last()
        self.assertEqual(new_slack_event.event_ts, "1234567890.654321")
        self.assertEqual(new_slack_event.event_type, "message")

        self.assertEqual(SlackAIChatMessage.objects.count(), initial_slack_chat_message_count + 1)
        new_message = SlackAIChatMessage.objects.last()
        self.assertEqual(new_message.slack_chat, self.slack_chat)
        self.assertEqual(new_message.user_message_slack_event, self.slack_event)
        self.assertEqual(new_message.output_slack_event, new_slack_event)
        self.assertIsNotNone(new_message.output_response_output_data)

    def test_process_message(self):
        mock_runner = MagicMock()
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_runner_instance.safe_run.return_value = "AI response"

        with patch.object(
            self.controller, "get_runner_class", return_value=mock_runner
        ), patch.object(self.controller, "get_formatted_message") as mock_format, patch.object(
            self.controller, "process_message_response"
        ) as mock_process:

            formatted_response = [
                (
                    "AI response",
                    [{"type": "section", "text": {"type": "mrkdwn", "text": "AI response"}}],
                )
            ]
            mock_format.return_value = formatted_response

            self.mock_slack_api_call(
                "conversations.info", response_data=self.conversations_info_data()
            )

            self.controller.process_message()

            mock_runner.assert_called_once_with(
                session=self.slack_chat.chat_session,
                user_input=self.slack_message_text,
                slack_context=self.controller.collect_slack_context(),
            )
            mock_runner_instance.safe_run.assert_called_once()
            mock_format.assert_called_once_with("AI response")
            mock_process.assert_called_once_with(formatted_response)

    def test_process_message_exception(self):
        mock_runner = MagicMock()
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_runner_instance.safe_run.side_effect = Exception("Test error")

        with patch.object(self.controller, "get_runner_class", return_value=mock_runner), patch(
            "baseapp_ai_langkit.slack.slack_ai_chat_controller.logger"
        ) as mock_logger:

            self.mock_slack_api_call(
                "conversations.info", response_data=self.conversations_info_data()
            )

            self.controller.process_message()

            mock_logger.exception.assert_called_once()
