from __future__ import annotations

import typing

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from model_utils.models import TimeStampedModel
from pgvector.django import VectorField

from baseapp_ai_langkit.embeddings.conf import app_settings
from baseapp_ai_langkit.embeddings.model_utils import available_content_types_query
from baseapp_ai_langkit.embeddings.querysets import GenericChunkQuerySet

if typing.TYPE_CHECKING:
    from baseapp_ai_langkit.embeddings.chunk_generators import BaseChunkGenerator


class EmbeddableModelMixin(models.Model):
    chunks = GenericRelation("baseapp_ai_langkit_embeddings.GenericChunk")
    embedding_error = models.TextField(null=True, blank=True)

    def chunk_generator_class(self) -> typing.Type[BaseChunkGenerator]:
        raise NotImplementedError("Subclasses must implement this method")

    def embeddable_content(self) -> typing.List[str]:
        raise NotImplementedError("Subclasses must implement this method")

    def save(self, *args, **kwargs):
        from baseapp_ai_langkit.embeddings.tasks import generate_vector_embeddings

        should_generate_embeddings = app_settings.SKIP_EMBEDDING_GENERATION
        if not should_generate_embeddings:
            skip_embedding_regeneration = kwargs.pop(
                "skip_embedding_regeneration", should_generate_embeddings
            )
        if not skip_embedding_regeneration:
            with self.embeddable_model_mixin_tracker:
                if any(
                    [
                        self.pk is None,
                        self.chunks.all().exists() is False,
                        *[
                            self.embeddable_model_mixin_tracker.has_changed(field)
                            for field in self.embeddable_model_mixin_tracker.fields
                        ],
                    ]
                ):
                    should_generate_embeddings = True
        super().save(*args, **kwargs)

        if should_generate_embeddings:
            # We delayed the embedding generation until after the save() method has completed
            # so that a pk has been generated for AutoFields.
            content_type = ContentType.objects.get_for_model(self.__class__)
            generate_vector_embeddings.delay(content_type.app_label, content_type.model, self.pk)

    class Meta:
        abstract = True


class GenericChunk(TimeStampedModel):
    # Generics
    content_type = models.ForeignKey(
        ContentType, limit_choices_to=available_content_types_query(), on_delete=models.CASCADE
    )
    object_id = models.CharField()
    content_object = GenericForeignKey("content_type", "object_id")

    # Base
    content = models.TextField(null=False, blank=False)
    embedding = VectorField(
        dimensions=app_settings.EMBEDDING_MODEL_DIMENSIONS, null=True, blank=True
    )

    objects = GenericChunkQuerySet.as_manager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.__class__.__name__}[{self.content_object}]"
