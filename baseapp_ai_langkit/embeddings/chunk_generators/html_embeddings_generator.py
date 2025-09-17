import json
import logging
import typing

from bs4 import BeautifulSoup
from django.db import transaction
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter

from baseapp_ai_langkit.embeddings.chunk_generators import BaseChunkGenerator
from baseapp_ai_langkit.embeddings.conf import app_settings
from baseapp_ai_langkit.embeddings.embedding_models import openai_embeddings
from baseapp_ai_langkit.embeddings.model_utils import validate_content_type_for_model
from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin, GenericChunk

logger = logging.getLogger(__name__)


class HTMLChunkGenerator(BaseChunkGenerator):
    """
    Implementation of the BaseChunkGenerator that handles html text-based content.
    """

    def generate_chunks(self, embeddable: EmbeddableModelMixin) -> typing.List[GenericChunk]:
        try:
            logger.info(
                f"Generating vector embeddings for {embeddable.__class__.__name__} {embeddable.id}"
            )
            validate_content_type_for_model(embeddable.__class__)

            # TODO: epic/rag Add a way to make the embeddings_model used more dynamic
            embeddings_model = openai_embeddings()
            # TODO: epic/rag Add a way to make the text splitter used more dynamic
            # The last chunk could be short (length ~TEXT_EMBEDDING_CHUNK_SIZE).
            # If this turns out to be a problem, we could do the following:
            # If the last chunk is too short, merge it manually with the second to last one.
            text_splitter = RecursiveCharacterTextSplitter.from_language(
                Language.HTML,
                chunk_size=app_settings.CHUNK_SIZE,
                chunk_overlap=app_settings.CHUNK_OVERLAP,
            )

            logger.info(
                "Generating vector embeddings. embeddings_model: {embeddings_model} text_splitter {text_splitter} text_splitter_parameters {text_splitter_parameters}".format(
                    embeddings_model=str(embeddings_model),
                    text_splitter=text_splitter.__class__.__name__,
                    text_splitter_parameters=json.dumps(
                        dict(
                            chunk_size=text_splitter._chunk_size,
                            chunk_overlap=text_splitter._chunk_overlap,
                        ),
                        indent=2,
                    ),
                )
            )

            embeddable_content = embeddable.embeddable_content()
            html_text_chunks = [
                text_chunk
                for embeddable_content_item in embeddable_content
                for text_chunk in text_splitter.split_text(embeddable_content_item)
                if text_chunk.strip()
            ]
            text_chunks = [
                BeautifulSoup(html_text_chunk, features="html.parser").get_text().strip()
                for html_text_chunk in html_text_chunks
            ]
            if len(text_chunks) > 0:
                logger.info(
                    f"Generating vector embeddings for Embeddable {embeddable.__class__.__name__} {embeddable.id}"
                )

                text_chunks = [text_chunk for text_chunk in text_chunks if len(text_chunk) > 0]
                text_chunk_embedding_pairs = zip(
                    text_chunks, embeddings_model.embed_documents(text_chunks)
                )

                with transaction.atomic():
                    logger.warning(
                        f"Deleting existing vector embeddings for Embeddable {embeddable.__class__.__name__} {embeddable.id}"
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
