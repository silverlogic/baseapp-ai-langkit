import logging
from typing import Any, List, Optional, Tuple, Type

from django.contrib.auth.base_user import AbstractBaseUser
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

    kwargs: dict
    slack_instance_controller: SlackInstanceController
    slack_event_data: dict

    slack_chat: SlackAIChat
    user_message_slack_event: SlackEvent
    user_message_text: str
    user_message_user: AbstractBaseUser

    runner_instance: BaseSlackChatInterface

    def __init__(self, slack_chat: SlackAIChat, user_message_slack_event: SlackEvent, **kwargs):
        self.slack_instance_controller = SlackInstanceController()
        self.slack_event_data = slack_chat.slack_event.data

        self.slack_chat = slack_chat
        self.user_message_slack_event = user_message_slack_event
        self.user_message_text = self.user_message_slack_event.data["event"]["text"]
        self.user_message_user, created = (
            self.slack_instance_controller.get_or_create_user_from_slack_user(
                self.user_message_slack_event.data["event"]["user"]
            )
        )

        self.kwargs = kwargs

    def process_message(self):
        try:
            llm_output = self.process_llm_output()
            message_chunks = self.get_formatted_message_chunks(llm_output)
            self.process_message_response(message_chunks)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            raise e

    def process_llm_output(self) -> Any:
        slack_context = self.collect_slack_context()
        runner_class = self.get_runner_class()

        self.runner_instance = runner_class(
            slack_context=slack_context,
            session=self.slack_chat.chat_session,
            user_input=self.user_message_text,
        )

        llm_output = self.runner_instance.safe_run()
        return llm_output

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
            context["current_user"] = self.user_message_user.email
        except SlackApiError as e:
            logging.exception(f"Request to Slack API Failed. {e.response['error']}")
        return context

    def get_formatted_message_chunks(self, llm_output: Any) -> list[Tuple[str, List[SlackBlock]]]:
        if not isinstance(llm_output, str):
            raise ValueError("The current slack formatter only supports strings as the LLM output.")

        max_text_length: int = 3000

        if len(llm_output) <= max_text_length:
            blocks = [dict(type="section", text=dict(type="mrkdwn", text=llm_output))]
            return [(llm_output, blocks)]

        chunks = []
        remaining_text = llm_output
        while len(remaining_text) > 0:
            if len(remaining_text) <= max_text_length:
                chunk_text = remaining_text
                blocks = [dict(type="section", text=dict(type="mrkdwn", text=chunk_text))]
                chunks.append((chunk_text, blocks))
                break

            # Find the last newline before the max length
            break_pos = remaining_text[:max_text_length].rfind("\n")

            # If no newline found or would result in empty chunk, break at max length
            if break_pos == -1 or break_pos == 0:
                break_pos = max_text_length - 1

            chunk_text = remaining_text[: break_pos + 1]
            blocks = [dict(type="section", text=dict(type="mrkdwn", text=chunk_text))]
            chunks.append((chunk_text, blocks))

            remaining_text = remaining_text[break_pos + 1 :].lstrip()
        return chunks

    def process_message_response(self, chunks: list[Tuple[str, List[SlackBlock]]]):
        previous_ts = None
        for text, blocks in chunks:
            output_slack_event_data = self.process_message_response_post_message(
                text, blocks, previous_ts
            )
            if output_slack_event_data is not None:
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
                previous_ts = output_slack_event_data["message"]["ts"]

    def process_message_response_post_message(
        self, text: str, blocks: list[SlackBlock], previous_ts: Optional[str] = None
    ) -> dict | None:
        slack_channel: str = self.slack_event_data["event"]["channel"]
        event_ts: Optional[str] = previous_ts or self.slack_event_data["event"]["event_ts"]

        response = self.slack_instance_controller.slack_web_client.chat_postMessage(
            channel=slack_channel,
            blocks=blocks,
            text=text,
            thread_ts=event_ts,
            unfurl_links=True,
        )
        response.validate()
        return response.data
