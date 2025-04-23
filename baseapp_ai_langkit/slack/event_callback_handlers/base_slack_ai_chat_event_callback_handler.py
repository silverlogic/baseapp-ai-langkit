from django.contrib.auth.models import AbstractBaseUser

from baseapp_ai_langkit.chats.models import ChatSession
from baseapp_ai_langkit.slack.event_callback_handlers.base_event_callback_handler import (
    BaseSlackAIChatEvent,
)
from baseapp_ai_langkit.slack.models import SlackAIChat


class BaseSlackAIChatEventCallbackHandler(BaseSlackAIChatEvent):
    slack_chat: SlackAIChat | None = None

    def get_slack_chat(self) -> SlackAIChat:
        return self.slack_chat

    def get_most_recent_slack_chat(
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

    def create_new_slack_chat(self, user: AbstractBaseUser) -> SlackAIChat:
        chat_session = ChatSession.objects.create(user=user)
        self.slack_chat = SlackAIChat.objects.create(
            chat_session=chat_session, slack_event=self.slack_event_callback.slack_event
        )
