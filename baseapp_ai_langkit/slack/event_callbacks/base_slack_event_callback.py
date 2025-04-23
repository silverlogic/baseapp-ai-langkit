import logging
from abc import ABC

from baseapp_ai_langkit.slack.models import SlackEvent
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

logger = logging.getLogger(__name__)


class BaseSlackEventCallback(ABC):
    slack_event: SlackEvent
    slack_instance_controller: SlackInstanceController

    data: dict
    team_id: str
    event_data: dict
    event_type: str

    class WarningException(Exception):
        """
        Non important exception that should just be logged as a warning
        """

        pass

    def __init__(self, slack_event_id: int):
        self.slack_event = SlackEvent.objects.get(id=slack_event_id)
        self.slack_instance_controller = self.get_slack_instance_controller()

    def get_slack_instance_controller(self) -> SlackInstanceController:
        """
        Override this method to provide a custom SlackInstanceController.
        """
        return SlackInstanceController()

    def __call__(self):
        self.slack_event.status = SlackEvent.STATUS.running
        self.slack_event.save()

        # TODO: consider using pydantic.
        self.data = self.slack_event.data
        self.team_id: str = self.data["team_id"]
        self.event_data: dict = self.data["event"]
        self.event_type: str = self.event_data["type"]

        try:
            handle_function = getattr(self, f"handle_{self.event_type}", None)
            if callable(handle_function):
                handle_function()
            else:
                raise Exception(f"Unable to handle event_type: {self.event_type}")
            self.slack_event.status = SlackEvent.STATUS.success
            self.slack_event.save()
        except self.WarningException as e:
            logger.warning(e)
            self.slack_event.status = SlackEvent.STATUS.success_with_warnings
            self.slack_event.save()
        except Exception as e:
            # TODO: Consider adding response to slack on error.
            logger.exception(e)
            self.slack_event.status = SlackEvent.STATUS.failed
            self.slack_event.save()

    def handle_tokens_revoked(self):
        """
        Handle `SlackEventCallbackData` with event_type `tokens_revoked`
        SEE https://api.slack.com/events/tokens_revoked
        """
        tokens = self.event_data.get("tokens", {})
        bot_user_ids = tokens.get("bot", [])
        raise self.WarningException(f"Event tokens_revoked for bot_user_ids: {bot_user_ids}")

    def handle_app_uninstalled(self):
        """
        Handle `SlackEventCallbackData` with event_type `app_uninstalled`
        SEE https://api.slack.com/events/app_uninstalled
        """
        raise self.WarningException(f"Event app_uninstalled for team_id: {self.team_id}")

    def handle_message(self):
        """
        Handle `SlackEventCallbackData` with event_type `message`
        """
        raise self.WarningException(f"Event message for team_id: {self.team_id}")

    def handle_app_mention(self):
        """
        Handle `SlackEventCallbackData` with event_type `app_mention`
        """
        raise self.WarningException(f"Event app_mention for team_id: {self.team_id}")

    def handle_reaction_added(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_added`
        """
        raise self.WarningException(f"Event reaction_added for team_id: {self.team_id}")

    def handle_reaction_removed(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_removed`
        """
        raise self.WarningException(f"Event reaction_removed for team_id: {self.team_id}")

    def handle_link_shared(self):
        """
        Handle `SlackEventCallbackData` with event_type `link_shared`
        """
        raise self.WarningException(f"Event link_shared for team_id: {self.team_id}")
