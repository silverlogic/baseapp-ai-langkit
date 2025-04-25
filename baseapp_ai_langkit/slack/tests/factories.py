import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.chats.tests.factories import ChatSessionFactory
from baseapp_ai_langkit.slack.models import SlackAIChat, SlackEvent, SlackEventStatus


class SlackEventFactory(DjangoModelFactory):
    class Meta:
        model = SlackEvent

    team_id = factory.Sequence(lambda n: f"T{n:019d}")
    event_ts = factory.Sequence(lambda n: f"1{n:020d}")
    event_type = factory.Faker("word")
    data = factory.Dict({"key": "value"})


class SlackEventStatusFactory(DjangoModelFactory):
    class Meta:
        model = SlackEventStatus

    slack_event = factory.SubFactory(SlackEventFactory)
    status = SlackEventStatus.STATUS.pending


class SlackAIChatFactory(DjangoModelFactory):
    class Meta:
        model = SlackAIChat

    celery_task_id = factory.Faker("uuid4")
    chat_session = factory.SubFactory(ChatSessionFactory)
    slack_event = factory.SubFactory(SlackEventFactory)
