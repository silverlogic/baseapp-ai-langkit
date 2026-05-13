from abc import ABC, abstractmethod
from typing import Any, ClassVar, List

from langchain_core.language_models import BaseLanguageModel


class LLMModelInitializer(ABC):
    """Abstract dispatcher for building a chat model from `(model_id, **params)`.

    Subclasses are registered via `@register_llm_initializer` and selected at runtime
    by matching `LLMRunnerNodeModelOverride.initializer_key` (or
    `AvailableLLMModel.initializer_key`) against `cls.key`. Built-in initializers ship
    with langkit (`openai`, `anthropic`, `gemini`, `openrouter`, `generic`); consumer
    projects can add custom ones (e.g., an internal gateway) with the same decorator.

    Subclasses MUST lazy-import their provider SDK inside `initialize()` so installing
    baseapp-ai-langkit does NOT require pulling every LangChain provider extra at once.
    """

    key: ClassVar[str]
    label: ClassVar[str]
    allowed_params: ClassVar[List[str]]

    @abstractmethod
    def initialize(self, model_id: str, **params: Any) -> BaseLanguageModel:
        raise NotImplementedError
