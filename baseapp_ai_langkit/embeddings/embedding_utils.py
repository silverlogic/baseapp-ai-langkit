from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Optional, Sequence

from django.db.models import QuerySet
from pgvector.django import CosineDistance

from baseapp_ai_langkit.embeddings.embedding_models import openai_embeddings
from baseapp_ai_langkit.embeddings.models import GenericChunk

logger = logging.getLogger(__name__)


def find_similar_chunks(
    query: str,
    embedding_model: Optional[object] = None,
    queryset: Optional[QuerySet] = None,
    embedding_field: str = "embedding",
    distance_metric: Optional[Callable[[str, Sequence[float]], Any]] = None,
    distance_filter: float = 0.5,
    filter_kwargs: Optional[Mapping[str, Any]] = None,
    order_by: str = "distance",
    top_k: Optional[int] = None,
) -> QuerySet:
    """
    Flexible semantic search over chunks.

    Args:
        query: Query text to embed and search.
        embedding_model: Embedding model instance or zero-arg factory. Defaults to openai_embeddings().
        queryset: Django queryset/manager to search. Defaults to GenericChunk.objects.all().
        embedding_field: Name of the vector field. Defaults to "embedding".
        distance_metric: Distance function. Defaults to CosineDistance.
        distance_filter: Max distance (smaller = more similar). Must be > 0. Defaults to 0.5.
        filter_kwargs: Extra filters for the queryset.
        order_by: Field to order by. Defaults to "distance".
        top_k: Limit results; if None returns all. Must be > 0 when provided.

    Returns:
        QuerySet annotated with "distance".
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")

    # Resolve embedding model (instance or factory)
    if embedding_model is None:
        model = openai_embeddings()
    elif callable(embedding_model) and not hasattr(embedding_model, "embed_query"):
        model = embedding_model()
    else:
        model = embedding_model

    if not hasattr(model, "embed_query"):
        raise TypeError("embedding_model must have an 'embed_query(text: str) -> vector' method")

    if queryset is None:
        queryset = GenericChunk.objects.all()
    else:
        queryset = queryset.all()  # normalize managers/querysets

    if distance_metric is None:
        distance_metric = CosineDistance

    if distance_filter <= 0:
        raise ValueError("distance_filter must be greater than 0")
    if top_k is not None and top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    # Get vector and coerce to plain list[float] for pgvector
    try:
        raw = model.embed_query(query)
        query_vector = [float(x) for x in raw]
    except Exception as exc:
        raise TypeError("Embedding model returned a non-numeric vector.") from exc

    filters = {"distance__isnull": False, "distance__lt": distance_filter}
    if filter_kwargs:
        filters.update(dict(filter_kwargs))

    qs = (
        queryset.annotate(distance=distance_metric(embedding_field, query_vector))
        .filter(**filters)
        .order_by(order_by)
        .defer(embedding_field)  # avoid pulling big vectors if not needed
    )

    if top_k is not None:
        qs = qs[:top_k]

    logger.info("similar_chunks qlen=%d top_k=%s dfilt=%.3f", len(query), top_k, distance_filter)
    return qs
