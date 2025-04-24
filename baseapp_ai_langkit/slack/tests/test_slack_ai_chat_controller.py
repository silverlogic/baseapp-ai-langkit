from unittest.mock import MagicMock, patch

from baseapp_ai_langkit.chats.models import ChatMessage
from baseapp_ai_langkit.slack.interfaces.slack_chat_runner import BaseSlackChatInterface
from baseapp_ai_langkit.slack.slack_ai_chat_controller import SlackAIChatController

from .factories import SlackAIChatFactory, SlackEventFactory
from .test import SlackTestCase


class TestSlackAIChatController(SlackTestCase):
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
        self.slack_chat = SlackAIChatFactory(slack_event=self.slack_event)
        self.slack_message_text = "Hello AI assistant"
        self.controller = SlackAIChatController(
            slack_chat=self.slack_chat, slack_message_text=self.slack_message_text
        )

    def test_get_runner(self):
        runner = self.controller.get_runner()
        self.assertTrue(issubclass(runner, BaseSlackChatInterface))

    def test_collect_slack_context(self):
        self.mock_slack_api_call("conversations.info", response_data=self.conversations_info_data())

        context = self.controller.collect_slack_context()

        self.assertEqual(context["channel_name"], "Slack Channel: pytest")

    def test_collect_slack_context_api_error(self):
        self.mock_slack_api_call("conversations.info", response_data={}, status=400)

        with patch("baseapp_ai_langkit.slack.slack_ai_chat_controller.logging") as mock_logging:
            context = self.controller.collect_slack_context()

            self.assertEqual(context, {})
            mock_logging.exception.assert_called_once()

    def test_save_chat_messages(self):
        llm_output = "I am an AI assistant"

        initial_count = ChatMessage.objects.count()

        self.controller.save_chat_messages(llm_output)

        self.assertEqual(ChatMessage.objects.count(), initial_count + 2)

        user_message = ChatMessage.objects.filter(
            session=self.slack_chat.chat_session,
            role=ChatMessage.ROLE_CHOICES.user,
            content=self.slack_message_text,
        ).first()

        assistant_message = ChatMessage.objects.filter(
            session=self.slack_chat.chat_session,
            role=ChatMessage.ROLE_CHOICES.assistant,
            content=llm_output,
        ).first()

        self.assertIsNotNone(user_message)
        self.assertIsNotNone(assistant_message)
        self.assertEqual(user_message.content, self.slack_message_text)
        self.assertEqual(assistant_message.content, llm_output)

    def test_process_message_response(self):
        llm_output = "I am an AI assistant"

        self.mock_slack_api_call("chat.postMessage")

        self.controller.process_message_response(llm_output)

        self.assert_slack_api_call(
            "chat.postMessage",
            expected_body={
                "channel": self.slack_event.data["event"]["channel"],
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": llm_output}}],
                "text": llm_output,
                "thread_ts": self.slack_event.data["event"]["event_ts"],
            },
        )

    def test_process_message_response_truncates_long_text(self):
        long_text = "A" * 4000

        with patch("baseapp_ai_langkit.slack.slack_ai_chat_controller.logger") as mock_logging:
            self.mock_slack_api_call("chat.postMessage")

            self.controller.process_message_response(long_text)

            truncated_text = long_text[:3000]
            expected_blocks = [dict(type="section", text=dict(type="mrkdwn", text=truncated_text))]

            self.assert_slack_api_call(
                "chat.postMessage",
                expected_body={
                    "channel": self.slack_event.data["event"]["channel"],
                    "blocks": expected_blocks,
                    "text": truncated_text,
                    "thread_ts": self.slack_event.data["event"]["event_ts"],
                },
            )
            mock_logging.warning.assert_called_once()

    def test_process_message(self):
        mock_runner = MagicMock()
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_runner_instance.safe_run.return_value = "AI response"

        with patch.object(self.controller, "get_runner", return_value=mock_runner):
            self.mock_slack_api_call("chat.postMessage")
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

            user_message = ChatMessage.objects.filter(
                session=self.slack_chat.chat_session,
                role=ChatMessage.ROLE_CHOICES.user,
                content=self.slack_message_text,
            ).first()

            assistant_message = ChatMessage.objects.filter(
                session=self.slack_chat.chat_session,
                role=ChatMessage.ROLE_CHOICES.assistant,
                content="AI response",
            ).first()

            self.assertIsNotNone(user_message)
            self.assertIsNotNone(assistant_message)

            expected_blocks = [dict(type="section", text=dict(type="mrkdwn", text="AI response"))]

            self.assert_slack_api_call(
                "chat.postMessage",
                expected_body={
                    "channel": self.slack_event.data["event"]["channel"],
                    "text": "AI response",
                    "blocks": expected_blocks,
                    "thread_ts": self.slack_event.data["event"]["event_ts"],
                },
            )

    def test_process_message_exception(self):
        mock_runner = MagicMock()
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_runner_instance.safe_run.side_effect = Exception("Test error")

        with patch.object(self.controller, "get_runner", return_value=mock_runner), patch(
            "baseapp_ai_langkit.slack.slack_ai_chat_controller.logger"
        ) as mock_logger:

            self.mock_slack_api_call(
                "conversations.info", response_data=self.conversations_info_data()
            )

            self.controller.process_message()

            mock_logger.exception.assert_called_once()
