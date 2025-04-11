import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.chats.models import (
    ChatIdentity,
    ChatMessage,
    ChatPrePromptedQuestion,
    ChatSession,
)
from baseapp_ai_langkit.tests.factories import UserFactory


class ChatSessionFactory(DjangoModelFactory):
    class Meta:
        model = ChatSession

    id = factory.Faker("uuid4")
    user = factory.SubFactory(UserFactory)


class ChatMessageFactory(DjangoModelFactory):
    class Meta:
        model = ChatMessage

    session = factory.SubFactory(ChatSessionFactory)
    role = factory.Iterator(["user", "assistant"])
    content = factory.Faker("text")


class ChatIdentityFactory(DjangoModelFactory):
    class Meta:
        model = ChatIdentity

    name = factory.Faker("name")
    avatar = factory.Faker("file_path")
    chat_intro_title = factory.Faker("sentence")
    chat_intro_subtitle = factory.Faker("sentence")
    chat_fab_text = factory.Faker("sentence")
    is_active = factory.Faker("boolean")


class ChatPrePromptedQuestionFactory(DjangoModelFactory):
    class Meta:
        model = ChatPrePromptedQuestion

    title = factory.Faker("sentence")
    prompt = factory.Faker("sentence")
    is_active = factory.Faker("boolean")
    order = factory.Faker("random_int")
