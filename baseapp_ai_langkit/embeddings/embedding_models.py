from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from baseapp_ai_langkit.embeddings.conf import app_settings


def openai_embeddings(
    *args, model_name: str = "text-embedding-3-small", **kwargs
) -> OpenAIEmbeddings:
    model_kwargs = {"dimensions": app_settings.EMBEDDING_MODEL_DIMENSIONS, **kwargs}
    return OpenAIEmbeddings(model=model_name, **model_kwargs)
