from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

from baseapp_ai_langkit.chats.models import ChatSession
from baseapp_ai_langkit.slack.event_callback_handlers.base_event_callback_handler import (
    BaseSlackAIChatEvent,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChat


class BaseSlackAIChatEventCallbackHandler(BaseSlackAIChatEvent):
    slack_chat: SlackAIChat | None = None

    def verify_if_is_bot(self):
        is_bot = "bot_id" in self.event_data
        if is_bot:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type: {self.event_type}. Reason: is_bot"
            )

    def verify_incoming_app(self):
        incoming_app_id = self.data.get("api_app_id", "")
        bot_app_id = settings.BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID
        if incoming_app_id != bot_app_id:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type: {self.event_type}. Reason: incoming_app_id != {bot_app_id}"
            )

    def get_slack_chat(self) -> SlackAIChat:
        return self.slack_chat

    def create_new_slack_chat(self, user: AbstractBaseUser) -> SlackAIChat:
        chat_session = ChatSession.objects.create(user=user)
        self.slack_chat = SlackAIChat.objects.create(
            chat_session=chat_session, slack_event=self.slack_event_callback.slack_event
        )
