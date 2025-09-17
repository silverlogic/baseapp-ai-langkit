import factory

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema


class BasePromptSchemaFactory(factory.Factory):
    description = factory.Faker("sentence")
    prompt = factory.Faker("text")
    required_placeholders = []
    placeholders_data = None
    conditional_rule = None

    class Meta:
        model = BasePromptSchema
