import typing

from django.db import models

from baseapp_ai_langkit.embeddings.chunk_generators import (
    BaseChunkGenerator,
    DefaultChunkGenerator,
    HTMLChunkGenerator,
)
from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin
from model_utils import FieldTracker
from model_utils.models import TimeStampedModel


class ExampleEmbeddable(EmbeddableModelMixin, TimeStampedModel):
    text = models.TextField(null=True, blank=True)

    # EmbeddableModelMixin Conformance
    embeddable_model_mixin_tracker = FieldTracker(fields=["text"])

    def chunk_generator_class(self) -> typing.Type[BaseChunkGenerator]:
        return DefaultChunkGenerator

    def embeddable_content(self) -> typing.List[str]:
        return [self.text or ""]


class ExampleHTMLEmbeddable(EmbeddableModelMixin, TimeStampedModel):
    html = models.TextField(null=True, blank=True)

    # EmbeddableModelMixin Conformance
    embeddable_model_mixin_tracker = FieldTracker(fields=["html"])

    def chunk_generator_class(self) -> typing.Type[BaseChunkGenerator]:
        return HTMLChunkGenerator

    def embeddable_content(self) -> typing.List[str]:
        return [self.html or ""]
