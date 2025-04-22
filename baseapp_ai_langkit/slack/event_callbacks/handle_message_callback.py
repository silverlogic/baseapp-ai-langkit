from django.contrib.auth.models import AbstractBaseUser

from baseapp_ai_langkit.chats.models import ChatSession
from baseapp_ai_langkit.slack.event_callbacks.base_handle_event_callback import (
    BaseHandleEventCallback,
)
from baseapp_ai_langkit.slack.event_callbacks.slack_event_callback import (
    SlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChat


class HandleMessageCallback(BaseHandleEventCallback):
    """
    Handle `SlackEventCallbackData` with event_type `message`
    """

    data: dict
    team_id: str
    event_data: dict
    event_type: str

    def __init__(
        self, data: dict, team_id: str, event_data: dict, event_type: str, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.data = data
        self.team_id = team_id
        self.event_data = event_data
        self.event_type = event_type

    def handle(self):
        self._verify_if_is_bot()
        self._verify_if_is_channel_type_and_is_in_thread()

        channel_type: str = self.event_data["channel_type"]  # channel or im
        event_user: str = self.event_data["user"]
        user, _ = (
            self.slack_event_callback.slack_instance_controller.get_or_create_user_from_slack_user(
                slack_user_id=event_user
            )
        )

        event_channel: str = self.event_data["channel"]
        slack_chat: SlackAIChat | None = None
        event_thread_ts: str = (
            self.event_data["thread_ts"] if "thread_ts" in self.event_data else None
        )

        if channel_type == "channel":
            slack_chat = self._get_most_recent_slack_chat(
                event_channel=event_channel, event_thread_ts=event_thread_ts
            )
        elif channel_type == "im":
            if event_thread_ts:
                slack_chat = self._get_most_recent_slack_chat(
                    event_channel=event_channel, event_thread_ts=event_thread_ts
                )
            else:
                slack_chat = self._create_new_slack_chat(user=user)

        if slack_chat is None:
            raise SlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: slack_chat is None"
            )

        if event_thread_ts and slack_chat.is_celery_task_processing:
            self.slack_event_callback.slack_instance_controller.slack_web_client.chat_postMessage(
                channel=event_channel,
                text=_("Please wait, still processing the previous message"),
                thread_ts=event_thread_ts,
            )
        else:
            event_text: str = self.event_data["text"]
            self.slack_event_callback.apply_process_incoming_user_slack_message_task(
                slack_chat=slack_chat,
                event_text=event_text,
            )

    def _verify_if_is_bot(self):
        is_bot = "bot_id" in self.event_data
        if is_bot:
            raise SlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: is_bot:{is_bot}"
            )

    def _verify_if_is_channel_type_and_is_in_thread(self):
        is_in_thread = "thread_ts" in self.event_data
        if self.event_data["channel_type"] == "channel" and is_in_thread is False:
            raise SlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: is_in_thread:{is_in_thread}"
            )

    def _get_most_recent_slack_chat(
        self, event_channel: str, event_thread_ts: str
    ) -> SlackAIChat | None:
        return (
            SlackAIChat.objects.filter(
                slack_event__data__event__channel=event_channel,
                slack_event__data__event__event_ts=event_thread_ts,
            )
            .order_by("-created")
            .first()
        )

    def _create_new_slack_chat(self, user: AbstractBaseUser) -> SlackAIChat:
        chat_session = ChatSession.objects.create(user=user)
        return SlackAIChat.objects.create(chat_session=chat_session, slack_event=self.slack_event)
