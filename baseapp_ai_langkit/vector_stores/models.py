import logging
from typing import Any, Dict, List, Tuple

from django.db import models
from langchain.tools import Tool
from langchain_openai import OpenAIEmbeddings
from model_utils.models import TimeStampedModel
from pgvector.django import CosineDistance, VectorField

logger = logging.getLogger(__name__)


class AbstractBaseVectorStore(TimeStampedModel):
    """
    An abstract base model for implementing vector stores, which provide methods
    for managing and querying vector embeddings.

    This model is designed to be subclassed, with subclasses required to
    implement key methods for embedding models, document addition, and similarity searches.

    Attributes:
        name (str): The unique name of the vector store.
        description (str): An optional description of the vector store.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name

    def get_embeddings_model(self):
        """
        Retrieve the embeddings model used by the vector store.

        This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement `get_embeddings_model`.")

    def add_documents(self, documents: List[Tuple[str, Dict[str, Any]]]) -> None:
        """
        Add documents to the vector store.

        This method must be implemented by subclasses.

        Args:
            documents (List[Tuple[str, Dict[str, Any]]]):
                A list of documents where each document is represented as a tuple
                of a string (document content) and metadata (key-value pairs).
        """
        raise NotImplementedError("Subclasses must implement `add_documents`.")

    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Perform a similarity search to retrieve the top `k` documents
        similar to the given query.

        This method must be implemented by subclasses.

        Args:
            query (str): The search query string.
            k (int, optional): The number of top results to return. Defaults to 4.

        Returns:
            List[Dict[str, Any]]:
                A list of dictionaries, where each dictionary represents a
                similar document and its metadata.
        """
        raise NotImplementedError("Subclasses must implement `similarity_search`.")

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["name"]),
        ]


class DefaultVectorStore(AbstractBaseVectorStore):
    # TODO: (Tech Debt) create manager for this model

    def get_embeddings_model(self):
        return OpenAIEmbeddings()

    def add_documents(self, documents: List[Tuple[str, Dict[str, Any]]]) -> None:
        embeddings_model = self.get_embeddings_model()

        contents = []
        metadatas = []

        for document, metadata in documents:
            metadata_str = " ".join(f"{key}: {value}" for key, value in metadata.items())
            combined_content = f"{document} {metadata_str}"

            contents.append(combined_content)
            metadatas.append(metadata)

        embeddings = embeddings_model.embed_documents(contents)

        for content, embedding, metadata in zip(contents, embeddings, metadatas):
            document_embedding, created = DefaultDocumentEmbedding.objects.update_or_create(
                vector_store=self,
                content=content,
                defaults={
                    "embedding": embedding,
                    "metadata": metadata,
                },
            )
            logger.info(
                f"{'Created new' if created else 'Updated'} embedding for document: {content}"
            )

    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        embeddings_model = self.get_embeddings_model()

        query_embedding = embeddings_model.embed_query(query)

        results = (
            DefaultDocumentEmbedding.objects.annotate(
                cosine_distance=CosineDistance("embedding", query_embedding)
            )
            .order_by("cosine_distance")
            .filter(
                vector_store=self,
                cosine_distance__isnull=False,
            )[:k]
        )

        return [
            {
                "content": result.content,
                "metadata": result.metadata,
            }
            for result in results
        ]


class DefaultDocumentEmbedding(TimeStampedModel):
    content = models.TextField()
    embedding = VectorField()
    metadata = models.JSONField(null=True, blank=True)
    vector_store = models.ForeignKey(
        DefaultVectorStore, on_delete=models.CASCADE, related_name="document_embeddings"
    )

    def __str__(self):
        return f"Embedding for vector store: {self.vector_store}"


class DefaultVectorStoreTool(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    vector_store = models.ForeignKey(
        DefaultVectorStore, on_delete=models.CASCADE, related_name="tools"
    )

    def __str__(self):
        return self.name

    def to_langchain_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
        )

    def tool_func(self, input_text: str) -> str:
        results = self.vector_store.similarity_search(input_text)
        return "\n".join([res["content"] for res in results])
