from __future__ import annotations

import logging

from django.db.models.manager import BaseManager

from baseapp_ai_langkit.embeddings.embedding_models import openai_embeddings
from baseapp_ai_langkit.embeddings.models import GenericChunk
from pgvector.django import CosineDistance

logger = logging.getLogger(__name__)


def find_similar_chunks(
    query: str, cosine_distance_filter: float = 0.5, filter_kwargs: dict = {}
) -> BaseManager[GenericChunk]:
    # TODO: epic/rag Add a way to make the embeddings model used more dynamic
    embeddings = openai_embeddings()
    query_vector = embeddings.embed_query(query)
    queryset = (
        GenericChunk.objects.annotate(cosine_distance=CosineDistance("embedding", query_vector))
        .filter(
            cosine_distance__isnull=False,
            cosine_distance__lt=cosine_distance_filter,
            **filter_kwargs,
        )
        .order_by("cosine_distance")
    )

    return queryset
