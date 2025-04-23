import inspect
import logging

from celery.result import AsyncResult

from baseapp_ai_langkit.slack import tasks
from baseapp_ai_langkit.slack.models import SlackAIChat, SlackEvent
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController

logger = logging.getLogger(__name__)


class SlackEventCallback:
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

    def handle(self):
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
                handle_function_signature = inspect.signature(handle_function)
                params = list(handle_function_signature.parameters.values())
                assert len(params) == 4
                assert all(
                    [
                        params[0].name == "data",
                        params[0].annotation == "dict",
                        params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ]
                )
                assert all(
                    [
                        params[1].name == "team_id",
                        params[1].annotation == "str",
                        params[1].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ]
                )
                assert all(
                    [
                        params[2].name == "event_data",
                        params[2].annotation == "dict",
                        params[2].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ]
                )
                assert all(
                    [
                        params[3].name == "event_type",
                        params[3].annotation == "str",
                        params[3].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ]
                )
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
        raise self.WarningException(f"Tokens revoked for bot_user_ids: {bot_user_ids}")

    def handle_app_uninstalled(self):
        """
        Handle `SlackEventCallbackData` with event_type `app_uninstalled`
        SEE https://api.slack.com/events/app_uninstalled
        """
        raise self.WarningException(f"App uninstalled for team_id: {self.team_id}")

    def handle_message(self):
        """
        Handle `SlackEventCallbackData` with event_type `message`
        """
        from baseapp_ai_langkit.slack.event_callbacks.message_callback_handler import HandleMessageCallback
        HandleMessageCallback(slack_event_callback=self).handle()

    def handle_app_mention(self):
        """
        Handle `SlackEventCallbackData` with event_type `app_mention`
        """
        from baseapp_ai_langkit.slack.event_callbacks.app_mention_callback_handler import HandleAppMentionCallback
        HandleAppMentionCallback(slack_event_callback=self).handle()

    def handle_reaction_added(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_added`
        """
        raise self.WarningException(f"Reaction added for team_id: {self.team_id}")

    def handle_reaction_removed(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_removed`
        """
        raise self.WarningException(f"Reaction removed for team_id: {self.team_id}")

    def handle_link_shared(self):
        """
        Handle `SlackEventCallbackData` with event_type `link_shared`
        """
        raise self.WarningException(f"Link shared for team_id: {self.team_id}")

    def apply_process_incoming_user_slack_message_task(
        self, slack_chat: SlackAIChat, event_text: str
    ):
        result: AsyncResult = tasks.process_incoming_user_slack_message.apply_async(
            kwargs=dict(
                slack_chat_id=slack_chat.id,
                slack_message_text=event_text,
            )
        )
        slack_chat.celery_task_id = result.id
        slack_chat.save()
