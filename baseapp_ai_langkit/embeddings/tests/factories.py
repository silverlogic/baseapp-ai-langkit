import factory
from django.contrib.contenttypes.models import ContentType

from baseapp_ai_langkit.embeddings.models import GenericChunk


class GenericChunkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GenericChunk

    content = factory.Faker("paragraph")
    embedding = None

    @classmethod
    def create_for_instance(cls, instance, **kwargs):
        """
        Create a GenericChunk for a specific model instance.

        Args:
            instance: The model instance to create a chunk for
            **kwargs: Additional attributes for the GenericChunk

        Returns:
            GenericChunk instance
        """
        content_type = ContentType.objects.get_for_model(instance.__class__)
        return cls.create(content_type=content_type, object_id=instance.pk, **kwargs)
