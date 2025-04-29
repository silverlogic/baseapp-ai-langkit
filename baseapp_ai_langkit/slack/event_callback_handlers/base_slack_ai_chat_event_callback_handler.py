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

    def verify_if_is_slack_chat_bot(self):
        is_bot = "bot_id" in self.event_data
        bot_app_id = self.event_data.get("app_id", None)
        if is_bot and bot_app_id:
            if bot_app_id == settings.BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID:
                raise BaseSlackEventCallback.WarningException(
                    f"Skipping event_type: {self.event_type}. Reason: is slack chat bot"
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

    def get_or_create_user_from_slack_event(self) -> AbstractBaseUser:
        if bot_id := self.event_data.get("bot_id", None):
            if event_subtype := self.event_data.get("subtype", None):
                if event_subtype == "bot_message":
                    user, created = (
                        self.slack_instance_controller.get_or_create_user_from_slack_bot(
                            bot_id=bot_id
                        )
                    )
                    return user
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type: {self.event_type}. Reason: event_subtype != bot_message"
            )
        else:
            if user := self.event_data.get("user", None):
                user, created = self.slack_instance_controller.get_or_create_user_from_slack_user(
                    slack_user_id=self.event_data["user"]
                )
                return user
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type: {self.event_type}. Reason: user not found"
            )
