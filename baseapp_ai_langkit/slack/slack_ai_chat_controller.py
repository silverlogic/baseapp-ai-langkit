import logging
from typing import Any, List, Optional, Tuple, Type

from pydantic import BaseModel
from slack_sdk.errors import SlackApiError

from baseapp_ai_langkit.slack.base.interfaces.slack_chat_runner import (
    BaseSlackChatInterface,
)
from baseapp_ai_langkit.slack.models import SlackAIChat, SlackAIChatMessage, SlackEvent
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

logger = logging.getLogger(__name__)


class SlackBlock(BaseModel):
    type: str
    text: str


class SlackAIChatController:
    """
    This class is responsible for connecting the Slack event with the desired LLM model.
    """

    slack_instance_controller: SlackInstanceController
    slack_event_data: dict

    slack_chat: SlackAIChat
    user_message_slack_event: SlackEvent
    user_message_text: str

    def __init__(self, slack_chat: SlackAIChat, user_message_slack_event: SlackEvent):
        self.slack_instance_controller = SlackInstanceController()
        self.slack_event_data = slack_chat.slack_event.data

        self.slack_chat = slack_chat
        self.user_message_slack_event = user_message_slack_event
        self.user_message_text = self.user_message_slack_event.data["event"]["text"]

    def process_message(self):
        slack_context = self.collect_slack_context()
        runner = self.get_runner_class()

        try:
            llm_output = runner(
                slack_context=slack_context,
                session=self.slack_chat.chat_session,
                user_input=self.user_message_text,
            ).safe_run()

            formatted_output = self.get_formatted_message(llm_output)
            self.process_message_response(formatted_output)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return

    def get_runner_class(self) -> Type[BaseSlackChatInterface]:
        """
        Override this method to change the runner.
        It must retrieve an implementation of BaseSlackChatInterface.

        Note:
        To avoid the dummy runner to be loaded, it's imported inside of the method.
        When using the actual runner, it's important to import it outside of the method so it can
        get registered in the Django admin.
        """
        from baseapp_ai_langkit.slack.runners.default_slack_chat_runner import (
            DefaultSlackChatRunner,
        )

        return DefaultSlackChatRunner

    def collect_slack_context(self) -> dict:
        context = {}
        try:
            response = self.slack_instance_controller.slack_web_client.conversations_info(
                channel=self.slack_event_data["event"]["channel"]
            )
            response.validate()
            channel_data = response.data["channel"]
            channel_name = channel_data.get("name", "N/A")
            context["channel_name"] = f"Slack Channel: {channel_name}"
            context["current_user"] = self.slack_chat.chat_session.user.email
        except SlackApiError as e:
            logging.exception(f"Request to Slack API Failed. {e.response['error']}")
        return context

    def get_formatted_message(self, llm_output: Any) -> list[Tuple[str, List[SlackBlock]]]:
        if not isinstance(llm_output, str):
            raise ValueError("The current slack formatter only supports strings as the LLM output.")

        max_text_length: int = 3000
        ellipsis = "..."
        effective_max_length = max_text_length - len(ellipsis)

        if len(llm_output) <= max_text_length:
            blocks = [dict(type="section", text=dict(type="mrkdwn", text=llm_output))]
            return [(llm_output, blocks)]

        chunks = []
        remaining_text = llm_output
        while len(remaining_text) > 0:
            # Last chunk doesn't need ellipsis
            if len(remaining_text) <= max_text_length:
                chunk_text = remaining_text
                blocks = [dict(type="section", text=dict(type="mrkdwn", text=chunk_text))]
                chunks.append((chunk_text, blocks))
                break

            chunk_text = remaining_text[:effective_max_length] + ellipsis
            blocks = [dict(type="section", text=dict(type="mrkdwn", text=chunk_text))]
            chunks.append((chunk_text, blocks))

            remaining_text = remaining_text[effective_max_length:]
        return chunks

    def process_message_response(self, formatted_chunks: list[Tuple[str, List[SlackBlock]]]):
        slack_channel: str = self.slack_event_data["event"]["channel"]
        event_ts: Optional[str] = self.slack_event_data["event"]["event_ts"]

        for text, blocks in formatted_chunks:
            response = self.slack_instance_controller.slack_web_client.chat_postMessage(
                channel=slack_channel,
                blocks=blocks,
                text=text,
                thread_ts=event_ts,
            )
            response.validate()
            output_slack_event_data = response.data
            output_slack_event = SlackEvent.objects.create(
                team_id=self.slack_event_data["team_id"],
                event_ts=output_slack_event_data["message"]["ts"],
                event_type=output_slack_event_data["message"]["type"],
                data=output_slack_event_data,
            )
            SlackAIChatMessage.objects.create(
                slack_chat=self.slack_chat,
                user_message_slack_event=self.user_message_slack_event,
                output_slack_event=output_slack_event,
                output_response_output_data=output_slack_event_data,
            )
