from typing import Any

from django.conf import settings
from langchain_core.language_models import BaseLanguageModel

from baseapp_ai_langkit.runners.model_initializers.base import LLMModelInitializer
from baseapp_ai_langkit.runners.model_initializers.registry import (
    register_llm_initializer,
)


@register_llm_initializer
class OpenRouterInitializer(LLMModelInitializer):
    """OpenRouter routes any provider's model via the OpenAI-compatible API.

    Implementation reuses `ChatOpenAI` from `langchain_openai` with OpenRouter's
    `base_url` and the consumer project's `OPENROUTER_API_KEY` setting.
    """

    key = "openrouter"
    label = "OpenRouter"
    allowed_params = ["temperature", "max_tokens", "top_p"]

    def initialize(self, model_id: str, **params: Any) -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI

        base_url = getattr(settings, "OPENROUTER_BASE_URL", None) or "https://openrouter.ai/api/v1"
        api_key = getattr(settings, "OPENROUTER_API_KEY", None)
        return ChatOpenAI(model=model_id, base_url=base_url, api_key=api_key, **params)
