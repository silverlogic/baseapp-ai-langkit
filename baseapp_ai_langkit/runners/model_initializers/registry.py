from typing import Dict, List, Optional, Type

from baseapp_ai_langkit.runners.model_initializers.base import LLMModelInitializer


class LLMModelInitializerRegistry:
    _registry: Dict[str, LLMModelInitializer] = {}

    @classmethod
    def register(cls, initializer_cls: Type[LLMModelInitializer]) -> Type[LLMModelInitializer]:
        existing = cls._registry.get(initializer_cls.key)
        if existing is not None and type(existing) is not initializer_cls:
            raise ValueError(
                f"LLMModelInitializer with key '{initializer_cls.key}' already registered "
                f"(existing: {type(existing).__name__}, attempted: {initializer_cls.__name__})"
            )
        cls._registry[initializer_cls.key] = initializer_cls()
        return initializer_cls

    @classmethod
    def get(cls, key: str) -> Optional[LLMModelInitializer]:
        return cls._registry.get(key)

    @classmethod
    def get_all(cls) -> List[LLMModelInitializer]:
        return list(cls._registry.values())

    @classmethod
    def keys(cls) -> List[str]:
        return list(cls._registry.keys())


def register_llm_initializer(
    initializer_cls: Type[LLMModelInitializer],
) -> Type[LLMModelInitializer]:
    LLMModelInitializerRegistry.register(initializer_cls)
    return initializer_cls
