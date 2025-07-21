from typing import List

from django.db import models
from model_utils import FieldTracker
from model_utils.models import TimeStampedModel

from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin


class ExampleEmbeddable(EmbeddableModelMixin, TimeStampedModel):
    text = models.TextField(null=True, blank=True)

    # EmbeddableModelMixin

    embeddable_model_mixin_tracker = FieldTracker(fields=["text"])

    def embeddable_content(self) -> List[str]:
        return [self.text or ""]
