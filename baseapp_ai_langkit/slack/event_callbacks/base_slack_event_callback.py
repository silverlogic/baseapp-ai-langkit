import logging

from baseapp_ai_langkit.slack.models import SlackEvent, SlackEventStatus
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

logger = logging.getLogger(__name__)


class BaseSlackEventCallback:
    slack_event: SlackEvent
    slack_instance_controller: SlackInstanceController

    data: dict
    team_id: str
    event_data: dict
    event_type: str

    class SkipException(Exception):
        """
        Exception that will skip the event callback and delete the slack event.
        """

        pass

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
        event_status = self.slack_event.event_statuses.last()
        event_status.status = SlackEventStatus.STATUS.running
        event_status.status_message = ""
        event_status.save()

        self.data = self.slack_event.data
        self.team_id: str = self.slack_event.team_id
        self.event_type: str = self.slack_event.event_type
        self.event_data: dict = self.data["event"]

        try:
            handle_function = getattr(self, f"handle_{self.event_type}", None)
            if callable(handle_function):
                handle_function()
            else:
                raise Exception(f"Unable to handle event_type: {self.event_type}")
            event_status.status = SlackEventStatus.STATUS.success
        except self.WarningException as e:
            logger.warning(f"Logging warning for team_id: {self.team_id} - {e}")
            event_status.status = SlackEventStatus.STATUS.success_with_warnings
            event_status.status_message = str(e)
        except Exception as e:
            self.handle_exception(e)
            logger.exception(f"Logging exception for team_id: {self.team_id} - {e}")
            event_status.status = SlackEventStatus.STATUS.failed
            event_status.status_message = str(e)
        finally:
            event_status.save(update_fields=["status", "status_message"])

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

    def handle_exception(self, error: Exception):
        """
        Handle an exception. This can be used to send an error response to slack.
        """
        pass
