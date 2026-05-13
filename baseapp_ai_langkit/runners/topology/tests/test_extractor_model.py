"""Tests for the F02-S02 `model` field in the topology payload + the root
`available_models` list. Asserts the no-SDK-at-extraction guarantee for the
new field (no initializer is invoked).
"""

from unittest.mock import patch

from django.test import TestCase

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
    LLMRunnerFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeModelOverrideFactory,
)
from baseapp_ai_langkit.runners.topology.extractor import extract_topology


class TestModelFieldDefault(TestCase):
    """Per-node `model` defaults come from runner.default_model_metadata."""

    def test_default_chat_runner_emits_real_defaults(self):
        """DefaultChatRunner declared default_model_metadata in S02 — extractor
        emits its initializer_key / model_id / params for every node."""
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        payload = extract_topology(record)
        self.assertIsNone(payload["error"])
        self.assertGreater(len(payload["nodes"]), 0)
        for node in payload["nodes"]:
            self.assertEqual(node["model"]["initializer_key"], "openai")
            self.assertEqual(node["model"]["model_id"], "gpt-4o-mini")
            self.assertEqual(node["model"]["params"], {"temperature": 0})
            self.assertIsNone(node["model"]["override"])

    def test_runner_without_default_model_metadata_emits_nulls(self):
        """A runner whose default_model_metadata is None → null/null/{} defaults.

        Approach: temporarily strip `default_model_metadata` from
        `DefaultChatRunner` (which declared it in this change) and re-run the
        extractor. Avoids spinning up a custom Runner + Workflow + LangGraph.
        """
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        original = DefaultChatRunner.default_model_metadata
        DefaultChatRunner.default_model_metadata = None
        try:
            payload = extract_topology(record)
        finally:
            DefaultChatRunner.default_model_metadata = original

        self.assertIsNone(payload["error"])
        for node in payload["nodes"]:
            self.assertIsNone(node["model"]["initializer_key"])
            self.assertIsNone(node["model"]["model_id"])
            self.assertEqual(node["model"]["params"], {})


class TestModelFieldOverride(TestCase):
    """Override row → `override` populated; `in_catalog` reflects catalog presence."""

    def test_in_catalog_true_when_catalog_row_matches(self):
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        node = LLMRunnerNodeFactory(runner=record, node="general_llm")
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
            params={"temperature": 0.2},
        )

        payload = extract_topology(record)

        node_payload = next(n for n in payload["nodes"] if n["key"] == "general_llm")
        override = node_payload["model"]["override"]
        self.assertEqual(override["initializer_key"], "anthropic")
        self.assertEqual(override["model_id"], "claude-sonnet-4-6")
        self.assertEqual(override["params"], {"temperature": 0.2})
        self.assertTrue(override["in_catalog"])
        self.assertIsInstance(override["saved_at"], str)

    def test_in_catalog_false_when_no_catalog_row_matches(self):
        """No matching AvailableLLMModel row → in_catalog: false."""
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        node = LLMRunnerNodeFactory(runner=record, node="general_llm")
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",
            model_id="claude-not-in-catalog",
        )

        payload = extract_topology(record)
        node_payload = next(n for n in payload["nodes"] if n["key"] == "general_llm")
        self.assertFalse(node_payload["model"]["override"]["in_catalog"])


class TestAvailableModelsRoot(TestCase):
    def test_root_includes_catalog_with_allowed_params_from_registry(self):
        AvailableLLMModelFactory(
            label="Claude",
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )

        payload = extract_topology(record)

        rows = payload["available_models"]
        keys = {(r["initializer_key"], r["model_id"]) for r in rows}
        self.assertIn(("openai", "gpt-4o-mini"), keys)  # seeded
        self.assertIn(("anthropic", "claude-sonnet-4-6"), keys)

        # OpenAI initializer is registered → allowed_params populated.
        openai_row = next(r for r in rows if r["initializer_key"] == "openai")
        self.assertEqual(openai_row["allowed_params"], ["temperature", "max_tokens", "top_p"])

    def test_unregistered_initializer_yields_empty_allowed_params(self):
        AvailableLLMModelFactory(initializer_key="unregistered_test_key", model_id="some-model")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )

        payload = extract_topology(record)

        row = next(
            r
            for r in payload["available_models"]
            if r["initializer_key"] == "unregistered_test_key"
        )
        self.assertEqual(row["allowed_params"], [])


class TestNoInitializerCalledDuringExtraction(TestCase):
    """Rule 14 / Decision 13: extractor must NOT invoke any initializer.initialize."""

    def test_no_initialize_call_during_extraction(self):
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        node = LLMRunnerNodeFactory(runner=record, node="general_llm")
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )

        with patch(
            "baseapp_ai_langkit.runners.model_initializers.anthropic"
            ".AnthropicInitializer.initialize"
        ) as mock_initialize:
            payload = extract_topology(record)

        self.assertIsNone(payload["error"])
        mock_initialize.assert_not_called()
