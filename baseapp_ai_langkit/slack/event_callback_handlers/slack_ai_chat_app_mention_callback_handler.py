from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)


class SlackAIChatAppMentionCallbackHandler(BaseSlackAIChatEventCallbackHandler):
    """
    Handle `SlackEventCallbackData` with event_type `app_mention`
    """

    def handle(self):
        self._verify_if_is_in_thread()

        event_user: str = self.event_data["user"]
        self.event_text: str = self.event_data["text"]

        user, _ = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=event_user
        )

        self.create_new_slack_chat(user=user)

    def _verify_if_is_in_thread(self):
        if "thread_ts" in self.event_data:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: is_in_thread"
            )
