from typing import Any

from langchain_core.language_models import BaseLanguageModel

from baseapp_ai_langkit.runners.model_initializers.base import LLMModelInitializer
from baseapp_ai_langkit.runners.model_initializers.registry import (
    register_llm_initializer,
)


@register_llm_initializer
class GenericInitializer(LLMModelInitializer):
    """Generic dispatcher to `langchain.chat_models.init_chat_model`.

    Expects `model_id` in the colon-prefixed form "provider:model" — e.g.
    "openai:gpt-4o-mini", "anthropic:claude-sonnet-4-6". The prefix is stripped
    and passed as LangChain's `model_provider` kwarg.
    """

    key = "generic"
    label = "Generic (init_chat_model)"
    allowed_params = ["temperature", "max_tokens", "top_p"]

    def initialize(self, model_id: str, **params: Any) -> BaseLanguageModel:
        from langchain.chat_models import init_chat_model

        if ":" not in model_id:
            raise ValueError(
                f"GenericInitializer requires colon-prefixed model_id "
                f"(e.g. 'openai:gpt-4o-mini'); got '{model_id}'"
            )
        provider, name = model_id.split(":", 1)
        return init_chat_model(name, model_provider=provider, **params)
