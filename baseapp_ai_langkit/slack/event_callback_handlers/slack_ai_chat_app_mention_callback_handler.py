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
        self.verify_incoming_app()
        self.verify_if_is_slack_chat_bot()
        self._verify_not_in_thread()

        self.event_text: str = self.event_data["text"]

        user = self.get_or_create_user_from_slack_event()
        self.create_new_slack_chat(user=user)

    def _verify_not_in_thread(self):
        if "thread_ts" in self.event_data:
            raise BaseSlackEventCallback.WarningException(
                f"Skipping event_type:{self.event_type}. Reason: is_in_thread"
            )
