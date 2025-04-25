import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.chats.tests.factories import ChatSessionFactory
from baseapp_ai_langkit.slack.models import (
    SlackAIChat,
    SlackAIChatMessage,
    SlackAIChatMessageReaction,
    SlackEvent,
    SlackEventStatus,
)
from baseapp_ai_langkit.tests.factories import UserFactory


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


class SlackAIChatMessageFactory(DjangoModelFactory):
    class Meta:
        model = SlackAIChatMessage

    slack_chat = factory.SubFactory(SlackAIChatFactory)
    user_message_slack_event = factory.SubFactory(SlackEventFactory)
    output_slack_event = factory.SubFactory(SlackEventFactory)
    output_response_output_data = factory.Dict({"response": "test response"})


class SlackAIChatMessageReactionFactory(DjangoModelFactory):
    class Meta:
        model = SlackAIChatMessageReaction

    user = factory.SubFactory(UserFactory)
    slack_chat_message = factory.SubFactory(SlackAIChatMessageFactory)
    reaction = factory.Faker(
        "random_element",
        elements=[
            *SlackAIChatMessageReaction.THUMBS_UP_REACTIONS,
            *SlackAIChatMessageReaction.THUMBS_DOWN_REACTIONS,
        ],
    )
    slack_event = factory.SubFactory(SlackEventFactory)
