import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.chats.tests.factories import ChatSessionFactory
from baseapp_ai_langkit.slack.models import SlackAIChat, SlackEvent


class SlackEventFactory(DjangoModelFactory):
    class Meta:
        model = SlackEvent

    data = factory.Dict({"key": "value"})
    status = SlackEvent.STATUS.pending


class SlackAIChatFactory(DjangoModelFactory):
    class Meta:
        model = SlackAIChat

    celery_task_id = factory.Faker("uuid4")
    chat_session = factory.SubFactory(ChatSessionFactory)
    slack_event = factory.SubFactory(SlackEventFactory)
