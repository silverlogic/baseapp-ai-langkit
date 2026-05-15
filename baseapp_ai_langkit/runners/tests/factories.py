import factory
from factory.django import DjangoModelFactory

from baseapp_ai_langkit.runners.models import (
    AvailableLLMModel,
    LLMRunner,
    LLMRunnerDefaultModelOverride,
    LLMRunnerNode,
    LLMRunnerNodeModelOverride,
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


class AvailableLLMModelFactory(DjangoModelFactory):
    class Meta:
        model = AvailableLLMModel
        django_get_or_create = ("initializer_key", "model_id")

    label = factory.Sequence(lambda n: f"Test model {n}")
    initializer_key = "openai"
    model_id = factory.Sequence(lambda n: f"gpt-test-{n}")
    default_params = factory.LazyFunction(dict)


class LLMRunnerNodeModelOverrideFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunnerNodeModelOverride

    runner_node = factory.SubFactory(LLMRunnerNodeFactory)
    initializer_key = "openai"
    model_id = "gpt-4o-mini"
    params = factory.LazyFunction(dict)


class LLMRunnerDefaultModelOverrideFactory(DjangoModelFactory):
    class Meta:
        model = LLMRunnerDefaultModelOverride

    runner = factory.SubFactory(LLMRunnerFactory)
    initializer_key = "openai"
    model_id = "gpt-4o-mini"
    params = factory.LazyFunction(dict)
