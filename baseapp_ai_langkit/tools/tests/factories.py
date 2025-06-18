import factory

from baseapp_ai_langkit.tools.models import DefaultTool
from baseapp_ai_langkit.vector_stores.tests.factories import DefaultVectorStoreFactory


class DefaultToolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DefaultTool

    name = factory.Sequence(lambda n: f"Tool {n}")
    description = factory.Faker("sentence")
    vector_store = factory.SubFactory(DefaultVectorStoreFactory)
