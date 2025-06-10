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

        with patch(
            "baseapp_ai_langkit.slack.slack_ai_chat_controller.SlackInstanceController.get_or_create_user_from_slack_user"
        ) as mock_get_user:
            mock_get_user.return_value = (self.slack_chat.chat_session.user, False)
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

    def test_get_formatted_message_chunks_short_text(self):
        llm_output = "I am an AI assistant"

        formatted_chunks = self.controller.get_formatted_message_chunks(llm_output)

        self.assertEqual(len(formatted_chunks), 1)
        text, blocks = formatted_chunks[0]
        self.assertEqual(text, llm_output)
        self.assertEqual(
            blocks, [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}]
        )

    def test_get_formatted_message_chunks_long_text(self):
        long_text = (
            """
This is a long sentence! Another sentence here? And one more sentence.
"""
            * 500
        )

        formatted_chunks = self.controller.get_formatted_message_chunks(long_text)

        self.assertTrue(len(formatted_chunks) > 1)

        total_text = ""
        for text, blocks in formatted_chunks:
            self.assertTrue(len(text) <= 3000)
            self.assertEqual(
                blocks, [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
            )
            total_text += text

        self.assertEqual(total_text.strip(), long_text.strip())

    def test_get_formatted_message_chunks_newline_breaks(self):
        text_with_newlines = "Line 1\nLine 2\nLine 3\n" * 1000

        formatted_chunks = self.controller.get_formatted_message_chunks(text_with_newlines)

        for text, blocks in formatted_chunks[:-1]:
            self.assertTrue(text.endswith("\n"))
            self.assertTrue(len(text) <= 3000)

    def test_get_formatted_message_chunks_no_newlines(self):
        continuous_text = "x" * 10000

        formatted_chunks = self.controller.get_formatted_message_chunks(continuous_text)

        for text, blocks in formatted_chunks[:-1]:
            self.assertEqual(len(text), 3000)

        combined = "".join(text for text, _ in formatted_chunks)
        self.assertEqual(combined, continuous_text)

    def test_get_formatted_message_chunks_edge_length(self):
        text_at_limit = "x" * 3000
        chunks = self.controller.get_formatted_message_chunks(text_at_limit)
        self.assertEqual(len(chunks), 1)

        text_over_limit = "x" * 3001
        chunks = self.controller.get_formatted_message_chunks(text_over_limit)
        self.assertEqual(len(chunks), 2)

    def test_get_formatted_message_chunks_non_string_input(self):
        with self.assertRaises(ValueError):
            self.controller.get_formatted_message_chunks(123)

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
                "unfurl_links": True,
            },
        )

    @patch(
        "baseapp_ai_langkit.slack.slack_ai_chat_controller.SlackAIChatController.process_message_response_post_message",
        return_value=None,
    )
    def test_process_message_response_none_output(self, mock_process_message_response_post_message):
        self.controller.process_message_response([("test", [])])
        mock_process_message_response_post_message.assert_called_once_with("test", [], None)

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
        ), patch.object(
            self.controller, "get_formatted_message_chunks"
        ) as mock_format, patch.object(
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

            with self.assertRaises(Exception) as context:
                self.controller.process_message()

            self.assertEqual(str(context.exception), "Test error")
            mock_logger.exception.assert_called_once()
