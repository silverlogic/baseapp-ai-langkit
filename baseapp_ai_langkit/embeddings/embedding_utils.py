from __future__ import annotations

import json
import logging
import typing

from django.db import transaction
from django.db.models.manager import BaseManager
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pgvector.django import CosineDistance

from baseapp_ai_langkit.embeddings.conf import app_settings
from baseapp_ai_langkit.embeddings.embedding_model import openai_embeddings
from baseapp_ai_langkit.embeddings.model_utils import validate_content_type_for_model
from baseapp_ai_langkit.embeddings.models import GenericChunk

if typing.TYPE_CHECKING:
    from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin

logger = logging.getLogger(__name__)


def generate_vector_embeddings(embeddable: EmbeddableModelMixin):
    try:
        logger.info(
            f"Generating vector embeddings for {embeddable.__class__.__name__} {embeddable.id}"
        )
        validate_content_type_for_model(embeddable.__class__)

        # TODO: epic/rag Add a way to make the embeddings model used more dynamic
        with openai_embeddings() as embeddings:
            logger.info(
                "Generating vector embeddings with model {model_name} and parameters {model_kwargs}".format(
                    model_name=embeddings.model,
                    model_kwargs=dict(dimensions=embeddings.dimensions),
                )
            )

            # TODO: epic/rag Add a way to make the text splitter used more dynamic
            # The last chunk could be short (length ~TEXT_EMBEDDING_CHUNK_SIZE).
            # If this turns out to be a problem, we could do the following:
            # If the last chunk is too short, merge it manually with the second to last one.
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=app_settings.CHUNK_SIZE,
                chunk_overlap=app_settings.CHUNK_OVERLAP,
            )

            logger.info(
                "Generating vector embeddings with text splitter {model_name} and parameters {model_kwargs}".format(
                    model_name=text_splitter.__class__.__name__,
                    model_kwargs=json.dumps(
                        dict(
                            chunk_size=text_splitter._chunk_size,
                            chunk_overlap=text_splitter._chunk_overlap,
                        ),
                        indent=2,
                    ),
                )
            )

            embeddable_content = embeddable.embeddable_content()
            text_chunks = [
                text_chunk
                for embeddable_content_item in embeddable_content
                for text_chunk in text_splitter.split_text(embeddable_content_item)
                if text_chunk.strip()
            ]
            if len(text_chunks) > 0:
                logger.info(
                    f"Generating vector embeddings for {embeddable.__class__.__name__} {embeddable.id}"
                )

                text_chunks = [text_chunk for text_chunk in text_chunks if len(text_chunk) > 0]
                text_chunk_embedding_pairs = zip(
                    text_chunks, embeddings.embed_documents(text_chunks)
                )

                with transaction.atomic():
                    logger.warning(
                        f"Deleting existing vector embeddings for {embeddable.__class__.__name__} {embeddable.id}"
                    )
                    embeddable.chunks.all().delete()

                    generic_chunks = GenericChunk.objects.bulk_create(
                        [
                            GenericChunk(
                                content_object=embeddable,
                                content=text_chunk_embedding_pair[0],
                                embedding=text_chunk_embedding_pair[1],
                            )
                            for text_chunk_embedding_pair in text_chunk_embedding_pairs
                        ]
                    )

                    if embeddable.embedding_error:
                        embeddable.embedding_error = None
                        embeddable.save(skip_embedding_regeneration=True)

                    logger.info(
                        f"Created {len(generic_chunks)} vector embeddings for {embeddable.__class__.__name__} {embeddable.id}"
                    )
    except Exception as e:
        logger.error(
            f"Error generating vector embeddings for {embeddable.__class__.__name__} {embeddable.id}: {e}",
            exc_info=True,
        )
        embeddable.embedding_error = str(e)
        embeddable.save(skip_embedding_regeneration=True)


def find_similar_chunks(
    query: str, cosine_distance_filter: float = 0.5, filter_kwargs: dict = {}
) -> BaseManager[GenericChunk]:
    # TODO: epic/rag Add a way to make the embeddings model used more dynamic
    with openai_embeddings() as embeddings:
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
