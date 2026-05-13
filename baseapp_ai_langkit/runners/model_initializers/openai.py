from typing import Any

from langchain_core.language_models import BaseLanguageModel

from baseapp_ai_langkit.runners.model_initializers.base import LLMModelInitializer
from baseapp_ai_langkit.runners.model_initializers.registry import (
    register_llm_initializer,
)


@register_llm_initializer
class OpenAIInitializer(LLMModelInitializer):
    key = "openai"
    label = "OpenAI"
    allowed_params = ["temperature", "max_tokens", "top_p"]

    def initialize(self, model_id: str, **params: Any) -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_id, **params)
