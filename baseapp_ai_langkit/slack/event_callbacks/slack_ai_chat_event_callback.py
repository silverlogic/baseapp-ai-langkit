import logging

from celery.result import AsyncResult

from baseapp_ai_langkit.slack.event_callback_handlers.base_slack_ai_chat_event_callback_handler import (
    BaseSlackAIChatEventCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_app_mention_callback_handler import (
    SlackAIChatAppMentionCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_exception_handler import (
    SlackAIChatExceptionHandler,
)
from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_message_callback_handler import (
    SlackAIChatMessageCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_reaction_added_callback_handler import (
    SlackAIChatReactionAddedCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_reaction_removed_callback_handler import (
    SlackAIChatReactionRemovedCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)

logger = logging.getLogger(__name__)


class SlackAIChatEventCallback(BaseSlackEventCallback):
    def handle_message(self):
        """
        Handle `SlackEventCallbackData` with event_type `message`
        """
        handler = SlackAIChatMessageCallbackHandler(slack_event_callback=self)
        handler.handle()
        self.apply_process_incoming_user_slack_message_task(handler=handler)

    def handle_app_mention(self):
        """
        Handle `SlackEventCallbackData` with event_type `app_mention`
        """
        handler = SlackAIChatAppMentionCallbackHandler(slack_event_callback=self)
        handler.handle()
        self.apply_process_incoming_user_slack_message_task(handler=handler)

    def handle_reaction_added(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_added`
        """
        handler = SlackAIChatReactionAddedCallbackHandler(slack_event_callback=self)
        handler.handle()

    def handle_reaction_removed(self):
        """
        Handle `SlackEventCallbackData` with event_type `reaction_removed`
        """
        handler = SlackAIChatReactionRemovedCallbackHandler(slack_event_callback=self)
        handler.handle()

    def handle_exception(self, error: Exception):
        """
        Handle `SlackEventCallbackData` exception
        """
        handler = SlackAIChatExceptionHandler(slack_event_callback=self)
        handler.handle()

    def apply_process_incoming_user_slack_message_task(
        self, handler: BaseSlackAIChatEventCallbackHandler, **kwargs
    ):
        from baseapp_ai_langkit.slack import tasks

        slack_chat = handler.get_slack_chat()
        result: AsyncResult = tasks.slack_process_incoming_user_slack_message.apply_async(
            kwargs=dict(
                slack_chat_id=slack_chat.id,
                user_message_slack_event_id=self.slack_event.id,
                **kwargs,
            )
        )
        slack_chat.celery_task_id = result.id
        slack_chat.save()
