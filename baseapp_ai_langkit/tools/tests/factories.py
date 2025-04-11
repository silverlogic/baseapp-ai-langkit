import factory
from langchain.tools import Tool

from baseapp_ai_langkit.tools.models import DefaultTool
from baseapp_ai_langkit.vector_stores.tests.factories import DefaultVectorStoreFactory


class ToolFactory(factory.Factory):
    name = factory.Sequence(lambda n: f"Tool {n}")
    description = factory.Faker("sentence")

    def tool_function(self, x):
        return x

    func = factory.LazyAttribute(lambda obj: obj.tool_function)

    class Meta:
        model = Tool


class DefaultToolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DefaultTool

    name = factory.Sequence(lambda n: f"Tool {n}")
    description = factory.Faker("sentence")
    vector_store = factory.SubFactory(DefaultVectorStoreFactory)
