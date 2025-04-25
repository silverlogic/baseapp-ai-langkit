from celery import shared_task

from baseapp_ai_langkit.slack.event_callbacks.slack_ai_chat_event_callback import (
    SlackAIChatEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChat, SlackEvent
from baseapp_ai_langkit.slack.slack_ai_chat_controller import SlackAIChatController


@shared_task
def slack_handle_event_hook_event_callback_data(slack_event_id: int):
    # TODO: Import EventCallback from setting.
    handler = SlackAIChatEventCallback(slack_event_id=slack_event_id)
    handler()


@shared_task
def slack_process_incoming_user_slack_message(slack_chat_id: int, user_message_slack_event_id: int):
    slack_chat = SlackAIChat.objects.get(id=slack_chat_id)
    user_message_slack_event = SlackEvent.objects.get(id=user_message_slack_event_id)

    # TODO Get SlackAIChatController from setting.
    runner = SlackAIChatController(
        slack_chat=slack_chat, user_message_slack_event=user_message_slack_event
    )
    runner.process_message()
