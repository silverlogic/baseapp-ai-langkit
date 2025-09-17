import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
)


class LLMRunnerFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunner

    name = factory.Faker("word")


class LLMRunnerNodeFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunnerNode

    runner = factory.SubFactory(LLMRunnerFactory)
    node = factory.Faker("word")


class LLMRunnerNodeUsagePromptFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunnerNodeUsagePrompt

    runner_node = factory.SubFactory(LLMRunnerNodeFactory)
    usage_prompt = factory.Faker("text")


class LLMRunnerNodeStateModifierFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunnerNodeStateModifier

    runner_node = factory.SubFactory(LLMRunnerNodeFactory)
    index = factory.Sequence(lambda n: n)
    state_modifier = factory.Faker("text")
