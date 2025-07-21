from __future__ import annotations

import typing

from django.contrib.contenttypes.models import ContentType
from django.db.models import BooleanField, ExpressionWrapper, Q, QuerySet


class GenericChunkQuerySet(QuerySet):
    def add_has_embedding(self) -> GenericChunkQuerySet:
        """
        Annotate has_embedding boolean.
        """
        return self.annotate(
            has_embedding=ExpressionWrapper(Q(embedding__isnull=False), output_field=BooleanField())
        )

    def filter_content_type(self, model_cls: typing.Type) -> GenericChunkQuerySet:
        """
        Filter by generic content_object class
        """
        return self.filter(content_type=ContentType.objects.get_for_model(model_cls))
