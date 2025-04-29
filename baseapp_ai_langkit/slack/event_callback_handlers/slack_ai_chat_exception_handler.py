import logging

from django.utils.translation import gettext_lazy as _

from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)

logger = logging.getLogger(__name__)


class SlackAIChatExceptionHandler(BaseSlackAIChatEventCallbackHandler):
    """
    Handle `SlackEventCallbackData` exception
    """

    def handle(self):
        self.verify_incoming_app()
        self.verify_if_is_slack_chat_bot()
        try:
            message = _(
                "Error while processing your request. Please try again later or contact support."
            )
            response = self.slack_instance_controller.slack_web_client.chat_postMessage(
                channel=self.event_data["channel"],
                blocks=[],
                text=str(message),
                thread_ts=self.event_data["event_ts"],
            )
            response.validate()
        except Exception as e:
            logger.exception(
                f"Error while sending error message to slack for team_id: {self.team_id} - {e}"
            )
