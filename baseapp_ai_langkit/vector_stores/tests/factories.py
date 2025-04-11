import factory

from baseapp_ai_langkit.vector_stores.models import (
    DefaultDocumentEmbedding,
    DefaultVectorStore,
)


class DefaultVectorStoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DefaultVectorStore

    name = factory.Sequence(lambda n: f"Vector Store {n}")
    description = factory.Faker("sentence")


class DefaultDocumentEmbeddingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DefaultDocumentEmbedding

    vector_store = factory.SubFactory(DefaultVectorStoreFactory)
    content = factory.Faker("sentence")
    embedding = [0.1, 0.2, 0.3]
    metadata = {"category": "test"}
