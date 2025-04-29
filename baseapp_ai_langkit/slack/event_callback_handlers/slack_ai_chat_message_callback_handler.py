from django.utils.translation import gettext_lazy as _

from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChat


class SlackAIChatMessageCallbackHandler(BaseSlackAIChatEventCallbackHandler):
    """
    Handle `SlackEventCallbackData` with event_type `message`
    """

    def handle(self):
        self.verify_incoming_app()
        self.verify_if_is_slack_chat_bot()
        self._verify_if_is_channel_type_and_is_in_thread()

        channel_type: str = self.event_data["channel_type"]  # channel or im
        event_channel: str = self.event_data["channel"]
        event_thread_ts: str = (
            self.event_data["thread_ts"] if "thread_ts" in self.event_data else None
        )

        if channel_type == "channel":
            self.slack_chat = self.get_most_recent_slack_chat(
                team_id=self.team_id, event_ts=event_thread_ts
            )
        elif channel_type == "im":
            if event_thread_ts:
                self.slack_chat = self.get_most_recent_slack_chat(
                    team_id=self.team_id, event_ts=event_thread_ts
                )
            else:
                user = self.get_or_create_user_from_slack_event()
                self.create_new_slack_chat(user=user)

        if self.slack_chat is None:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: slack_chat is None"
            )

        if event_thread_ts and self.slack_chat.is_celery_task_processing:
            self.slack_instance_controller.slack_web_client.chat_postMessage(
                channel=event_channel,
                text=_("Please wait, still processing the previous message"),
                thread_ts=event_thread_ts,
            )
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: slack_chat.is_celery_task_processing"
            )

    def _verify_if_is_channel_type_and_is_in_thread(self):
        is_in_thread = "thread_ts" in self.event_data
        if self.event_data["channel_type"] == "channel" and is_in_thread is False:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type: {self.event_type}. Reason: is_in_thread:{is_in_thread}"
            )

    def get_most_recent_slack_chat(self, team_id: str, event_ts: str) -> SlackAIChat | None:
        try:
            return SlackAIChat.objects.get(
                slack_event__team_id=team_id,
                slack_event__event_ts=event_ts,
                slack_event__event_type__in=["message", "app_mention"],
            )
        except SlackAIChat.DoesNotExist:
            return None
