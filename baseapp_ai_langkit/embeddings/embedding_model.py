from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from langchain_openai import OpenAIEmbeddings

from baseapp_ai_langkit.embeddings.conf import app_settings


@contextmanager
def openai_embeddings(*args, **kwds) -> Generator[OpenAIEmbeddings, None, None]:
    model_name = "text-embedding-3-small"
    model_kwargs = {"dimensions": app_settings.EMBEDDING_MODEL_DIMENSIONS}
    embeddings = OpenAIEmbeddings(model=model_name, **model_kwargs)
    yield embeddings
