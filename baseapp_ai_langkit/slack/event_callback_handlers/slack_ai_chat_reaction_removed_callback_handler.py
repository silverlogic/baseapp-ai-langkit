from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChatMessageReaction


class SlackAIChatReactionRemovedCallbackHandler(BaseSlackAIChatEventCallbackHandler):
    """
    Handle `SlackEventCallbackData` with event_type `reaction_removed`
    """

    def handle(self):
        self.verify_incoming_app()

        event_user: str = self.event_data["user"]
        event_item_ts: str = self.event_data["item"]["ts"]
        reaction = self.event_data["reaction"]

        user, _ = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=event_user
        )

        try:
            reaction_instance = SlackAIChatMessageReaction.objects.get(
                user=user,
                reaction=reaction,
                slack_chat_message__output_slack_event__team_id=self.team_id,
                slack_chat_message__output_slack_event__event_ts=event_item_ts,
            )
        except SlackAIChatMessageReaction.DoesNotExist as e:
            raise BaseSlackEventCallback.WarningException(str(e))

        reaction_instance.delete()
