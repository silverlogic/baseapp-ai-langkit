from celery import shared_task
from django.conf import settings
from django.utils.module_loading import import_string

from baseapp_ai_langkit.slack.models import SlackAIChat, SlackEvent


@shared_task
def slack_handle_event_hook_event_callback_data(slack_event_id: int):
    EventCallbackClass = import_string(settings.BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK)
    handler = EventCallbackClass(slack_event_id=slack_event_id)
    handler()


@shared_task
def slack_process_incoming_user_slack_message(
    slack_chat_id: int, user_message_slack_event_id: int, **kwargs
):
    slack_chat = SlackAIChat.objects.get(id=slack_chat_id)
    user_message_slack_event = SlackEvent.objects.get(id=user_message_slack_event_id)

    ControllerClass = import_string(settings.BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER)
    runner = ControllerClass(
        slack_chat=slack_chat, user_message_slack_event=user_message_slack_event, **kwargs
    )
    runner.process_message()
