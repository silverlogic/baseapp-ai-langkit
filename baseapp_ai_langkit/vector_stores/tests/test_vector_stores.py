from unittest.mock import MagicMock, patch

import pytest

from baseapp_ai_langkit.vector_stores.models import DefaultDocumentEmbedding
from baseapp_ai_langkit.vector_stores.tests.factories import (
    DefaultDocumentEmbeddingFactory,
    DefaultVectorStoreFactory,
)

pytestmark = pytest.mark.django_db


def test_default_vector_store_str():
    store = DefaultVectorStoreFactory(name="My Store")
    assert str(store) == "My Store"


def test_default_document_embedding_str():
    embedding = DefaultDocumentEmbeddingFactory()
    assert str(embedding) == f"Embedding for vector store: {embedding.vector_store}"


@patch("baseapp_ai_langkit.vector_stores.models.DefaultVectorStore.get_embeddings_model")
def test_default_vector_store_add_documents(mock_get_embeddings_model):
    store = DefaultVectorStoreFactory()
    mock_embeddings_model = MagicMock()
    mock_embeddings_model.embed_documents.return_value = [[0.4, 0.5], [0.6, 0.7]]
    mock_get_embeddings_model.return_value = mock_embeddings_model

    documents = [
        ("Document 1 text", {"source": "Test Source 1"}),
        ("Another document text", {"source": "Test Source 2"}),
    ]
    store.add_documents(documents)

    embeddings = DefaultDocumentEmbedding.objects.filter(vector_store=store).order_by("id")
    assert embeddings.count() == 2

    first = embeddings[0]
    assert first.content == "Document 1 text source: Test Source 1"
    assert first.metadata["source"] == "Test Source 1"
    assert list(first.embedding) == pytest.approx([0.4, 0.5])

    second = embeddings[1]
    assert second.content == "Another document text source: Test Source 2"
    assert second.metadata["source"] == "Test Source 2"
    assert list(second.embedding) == pytest.approx([0.6, 0.7])

    mock_embeddings_model.embed_documents.assert_called_once_with(
        ["Document 1 text source: Test Source 1", "Another document text source: Test Source 2"]
    )


@patch("baseapp_ai_langkit.vector_stores.models.DefaultVectorStore.get_embeddings_model")
def test_default_vector_store_similarity_search(mock_get_embeddings_model):
    store = DefaultVectorStoreFactory()

    doc1 = DefaultDocumentEmbeddingFactory(
        vector_store=store,
        content="Python is a versatile programming language.",
        embedding=[0.1, 0.1],
        metadata={"category": "programming"},
    )
    doc2 = DefaultDocumentEmbeddingFactory(
        vector_store=store,
        content="Paris is the capital of France.",
        embedding=[0.9, 0.9],
        metadata={"category": "geography"},
    )

    mock_embeddings_model = MagicMock()
    mock_embeddings_model.embed_query.return_value = [0.0, 0.0]
    mock_get_embeddings_model.return_value = mock_embeddings_model

    results = store.similarity_search("What is Python?")

    assert len(results) == 2
    assert results[0]["content"] == doc1.content
    assert results[1]["content"] == doc2.content

    mock_embeddings_model.embed_query.assert_called_once_with("What is Python?")
