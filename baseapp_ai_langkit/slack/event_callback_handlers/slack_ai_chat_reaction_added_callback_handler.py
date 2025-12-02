from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import (
    SlackAIChatMessage,
    SlackAIChatMessageReaction,
)


class SlackAIChatReactionAddedCallbackHandler(BaseSlackAIChatEventCallbackHandler):
    """
    Handle `SlackEventCallbackData` with event_type `reaction_added`
    """

    def handle(self):
        self.verify_incoming_app()

        event_user: str = self.event_data["user"]
        event_item_ts: str = self.event_data["item"]["ts"]
        reaction = self.event_data["reaction"]

        try:
            slack_chat_message = SlackAIChatMessage.objects.get(
                output_slack_event__team_id=self.team_id,
                output_slack_event__event_ts=event_item_ts,
            )
        except SlackAIChatMessage.DoesNotExist as e:
            raise BaseSlackEventCallback.WarningException(str(e))

        user, _ = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=event_user
        )

        SlackAIChatMessageReaction.objects.create(
            user=user,
            slack_chat_message=slack_chat_message,
            reaction=reaction,
            slack_event=self.slack_event_callback.slack_event,
        )
