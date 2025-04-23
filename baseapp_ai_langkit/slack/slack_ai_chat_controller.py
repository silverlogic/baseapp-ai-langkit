import logging
from typing import Optional, Type

from rest_framework import serializers
from slack_sdk.errors import SlackApiError

from baseapp_ai_langkit.chats.models import ChatMessage
from baseapp_ai_langkit.chats.rest_framework.serializers import ChatMessageSerializer
from baseapp_ai_langkit.slack.interfaces.slack_chat_runner import BaseSlackChatInterface
from baseapp_ai_langkit.slack.models import SlackAIChat
from baseapp_ai_langkit.slack.runners.slack_dummy_runner import SlackDummyRunner
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

logger = logging.getLogger(__name__)


class SlackAIChatController:
    slack_chat: SlackAIChat
    slack_message_text: str
    slack_instance_controller: SlackInstanceController
    slack_event_data: dict

    def __init__(self, slack_chat: SlackAIChat, slack_message_text: str):
        self.slack_chat = slack_chat
        self.slack_message_text = slack_message_text
        self.slack_instance_controller = SlackInstanceController()
        self.slack_event_data = self.slack_chat.slack_event.data["event"]

    def process_message(self):
        slack_context = self.collect_slack_context()
        runner = self.get_runner()

        try:
            llm_output = runner(
                session=self.slack_chat.chat_session,
                user_input=self.slack_message_text,
                slack_context=slack_context,
            ).safe_run()

            self.save_chat_messages(llm_output)
            self.process_message_response(llm_output)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return

    def get_runner(self) -> Type[BaseSlackChatInterface]:
        """
        Override this method to change the runner.
        It must retrieve an implementation of BaseSlackChatInterface.
        """
        return SlackDummyRunner

    def collect_slack_context(self) -> dict:
        context = {}
        try:
            response = self.slack_instance_controller.slack_web_client.conversations_info(
                channel=self.slack_event_data["channel"]
            )
            response.validate()
            channel_data = response.data["channel"]
            channel_name = channel_data.get("name", "N/A")
            context["channel_name"] = f"Slack Channel: {channel_name}"
        except SlackApiError as e:
            logging.exception(f"Request to Slack API Failed. {e.response['error']}")
        return context

    def save_chat_messages(self, llm_output: str):
        data = {
            "session": self.slack_chat.chat_session.id,
            "role": ChatMessage.ROLE_CHOICES.user,
            "content": self.slack_message_text,
        }
        user_message_serializer = self.get_message_serializer(data=data)
        user_message_serializer.is_valid(raise_exception=True)
        user_message_serializer.save()

        data = {
            "session": self.slack_chat.chat_session.id,
            "role": ChatMessage.ROLE_CHOICES.assistant,
            "content": llm_output,
        }
        assistant_message_serializer = self.get_message_serializer(data=data)
        assistant_message_serializer.is_valid(raise_exception=True)
        assistant_message_serializer.save()

    def get_message_serializer(self, data: dict) -> Type[serializers.ModelSerializer]:
        return ChatMessageSerializer(data=data)

    def process_message_response(self, llm_output: str):
        slack_channel: str = self.slack_event_data["channel"]
        event_ts: Optional[str] = self.slack_event_data.get("event_ts", None)

        max_text_length: int = 3000
        text = llm_output
        if len(text) > max_text_length:
            logger.warning(
                f"Truncating message: because it is too long ({len(text)} > {max_text_length})"
            )
            text = llm_output[:max_text_length]

        blocks = [dict(type="section", text=dict(type="mrkdwn", text=text))]

        response = self.slack_instance_controller.slack_web_client.chat_postMessage(
            channel=slack_channel,
            blocks=blocks,
            text=text,
            thread_ts=event_ts,
        )

        response.validate()
