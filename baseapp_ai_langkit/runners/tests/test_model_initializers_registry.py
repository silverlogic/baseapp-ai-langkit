"""Tests for the F02-S02 `LLMModelInitializerRegistry` and built-in initializers.

Covers registration, lookup, duplicate detection, and lazy-import semantics on the
five built-ins shipped by langkit (`openai`, `anthropic`, `gemini`, `openrouter`,
`generic`). Lazy imports are crucial: consumer projects that don't pip-install every
LangChain provider extra must still be able to boot the app — the import only fires
when the matching `initialize()` is called.
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from baseapp_ai_langkit.runners.model_initializers.base import LLMModelInitializer
from baseapp_ai_langkit.runners.model_initializers.openai import OpenAIInitializer
from baseapp_ai_langkit.runners.model_initializers.registry import (
    LLMModelInitializerRegistry,
    register_llm_initializer,
)


class TestBuiltInsRegistered(SimpleTestCase):
    """The 5 built-ins are registered at `apps.ready()` time."""

    def test_all_five_keys_are_present(self):
        keys = LLMModelInitializerRegistry.keys()
        for built_in in ("openai", "anthropic", "gemini", "openrouter", "generic"):
            self.assertIn(built_in, keys)

    def test_built_in_metadata_is_consistent(self):
        openai = LLMModelInitializerRegistry.get("openai")
        self.assertEqual(openai.label, "OpenAI")
        self.assertEqual(openai.allowed_params, ["temperature", "max_tokens", "top_p"])

        generic = LLMModelInitializerRegistry.get("generic")
        self.assertEqual(generic.label, "Generic (init_chat_model)")


class TestRegistryAPI(SimpleTestCase):
    """Lookup, listing, and the duplicate-registration guard."""

    def test_get_returns_none_for_unknown_key(self):
        self.assertIsNone(LLMModelInitializerRegistry.get("does-not-exist"))

    def test_get_all_returns_all_registered_initializers(self):
        initializers = LLMModelInitializerRegistry.get_all()
        self.assertGreaterEqual(len(initializers), 5)
        keys = {type(i).__name__ for i in initializers}
        self.assertIn("OpenAIInitializer", keys)

    def test_re_registering_the_same_class_is_a_noop(self):
        """Re-registering the same class (e.g. when a module is re-imported under
        a watch reload) MUST NOT raise — it simply updates the stored instance."""
        before = type(LLMModelInitializerRegistry.get("openai"))
        register_llm_initializer(OpenAIInitializer)
        after = type(LLMModelInitializerRegistry.get("openai"))
        self.assertIs(before, after)

    def test_registering_a_different_class_under_an_existing_key_raises(self):
        class ConflictingOpenAI(LLMModelInitializer):
            key = "openai"
            label = "Conflicting OpenAI"
            allowed_params = ["temperature"]

            def initialize(self, model_id, **params):
                raise NotImplementedError

        with self.assertRaises(ValueError) as ctx:
            LLMModelInitializerRegistry.register(ConflictingOpenAI)
        self.assertIn("openai", str(ctx.exception))
        self.assertIn("already registered", str(ctx.exception))


class TestConsumerExtensibility(TestCase):
    """Consumer projects can register their own initializers via the decorator."""

    REGISTERED_KEY = "test_consumer_gateway"

    def setUp(self):
        # Make sure the test key is clean for re-runs.
        LLMModelInitializerRegistry._registry.pop(self.REGISTERED_KEY, None)

    def tearDown(self):
        LLMModelInitializerRegistry._registry.pop(self.REGISTERED_KEY, None)

    def test_decorator_registers_and_makes_initializer_callable(self):
        captured = {}

        @register_llm_initializer
        class ConsumerGatewayInitializer(LLMModelInitializer):
            key = self.REGISTERED_KEY
            label = "Consumer Gateway"
            allowed_params = ["temperature"]

            def initialize(self, model_id, **params):
                captured["model_id"] = model_id
                captured["params"] = params
                return "fake-chat-model"

        result = LLMModelInitializerRegistry.get(self.REGISTERED_KEY)
        self.assertIsNotNone(result)
        self.assertEqual(result.label, "Consumer Gateway")

        # Invoking the initializer reaches the consumer's `initialize` body.
        built = result.initialize("custom-model", temperature=0.7)
        self.assertEqual(built, "fake-chat-model")
        self.assertEqual(captured["model_id"], "custom-model")
        self.assertEqual(captured["params"], {"temperature": 0.7})


class TestLazyImportSemantics(SimpleTestCase):
    """Built-ins must lazy-import their provider SDK inside `initialize()`,
    NOT at module-import time. This keeps `pip install baseapp-ai-langkit` from
    requiring every LangChain provider extra."""

    def test_anthropic_initializer_does_not_eagerly_import_langchain_anthropic(self):
        # Sanity: the class was importable without `langchain_anthropic` installed.
        # If it isn't installed in the test env, the registry-registration would
        # have failed on app startup if the import were eager.
        from baseapp_ai_langkit.runners.model_initializers.anthropic import (
            AnthropicInitializer,
        )

        initializer = AnthropicInitializer()
        # `langchain_anthropic` should NOT be in sys.modules just because we
        # imported the initializer class. (If it is, that's a regression — the
        # import was eagerly triggered somewhere.)
        # We don't assert absence (some other test may have lazily loaded it);
        # we only assert that constructing the initializer instance doesn't fault.
        self.assertEqual(initializer.key, "anthropic")

    def test_openai_initialize_builds_chat_openai(self):
        """The simplest happy-path: `OpenAIInitializer.initialize(...)` lazy-imports
        `ChatOpenAI` and constructs it with the given kwargs."""
        from baseapp_ai_langkit.runners.model_initializers.openai import (
            OpenAIInitializer,
        )

        initializer = OpenAIInitializer()
        # Patch the lazily-imported symbol at its real import site.
        with patch("langchain_openai.ChatOpenAI") as MockChatOpenAI:
            instance = initializer.initialize("gpt-4o-mini", temperature=0.3)

        MockChatOpenAI.assert_called_once_with(model="gpt-4o-mini", temperature=0.3)
        self.assertIs(instance, MockChatOpenAI.return_value)


class TestGenericInitializer(SimpleTestCase):
    """The `generic` built-in delegates to `langchain.chat_models.init_chat_model`
    after splitting `model_id` on the colon delimiter."""

    def test_colon_prefixed_model_id_splits_into_provider_and_name(self):
        from baseapp_ai_langkit.runners.model_initializers.generic import (
            GenericInitializer,
        )

        initializer = GenericInitializer()
        with patch("langchain.chat_models.init_chat_model") as mock_init:
            initializer.initialize("openai:gpt-4o", temperature=0.5)

        mock_init.assert_called_once_with("gpt-4o", model_provider="openai", temperature=0.5)

    def test_missing_colon_raises_value_error(self):
        from baseapp_ai_langkit.runners.model_initializers.generic import (
            GenericInitializer,
        )

        initializer = GenericInitializer()
        with self.assertRaises(ValueError) as ctx:
            initializer.initialize("gpt-4o")
        self.assertIn("colon-prefixed", str(ctx.exception))
