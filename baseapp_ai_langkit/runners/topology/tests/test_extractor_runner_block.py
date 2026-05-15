"""Tests for the F03-S01 root `runner` block in the topology payload + the
`_resolve_runner_label` helper. Asserts the no-SDK-at-extraction guarantee
extends to the new rung (no initializer is invoked for the runner-level
override).
"""

from unittest.mock import patch

from django.test import TestCase

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
    LLMRunnerDefaultModelOverrideFactory,
    LLMRunnerFactory,
)
from baseapp_ai_langkit.runners.topology.extractor import (
    _resolve_runner_label,
    extract_topology,
)


class TestResolveRunnerLabel(TestCase):
    def test_returns_declared_label_when_set(self):
        """A runner class with `label = "Custom"` returns "Custom" unchanged."""
        original = DefaultChatRunner.label
        DefaultChatRunner.label = "Custom Label"
        try:
            self.assertEqual(_resolve_runner_label(DefaultChatRunner), "Custom Label")
        finally:
            DefaultChatRunner.label = original

    def test_falls_back_to_class_name_when_label_is_none(self):
        """A runner class with `label = None` returns `runner_class.__name__`
        (class name only, NOT the dotted path stored in `LLMRunner.name`)."""
        original = DefaultChatRunner.label
        DefaultChatRunner.label = None
        try:
            self.assertEqual(_resolve_runner_label(DefaultChatRunner), "DefaultChatRunner")
        finally:
            DefaultChatRunner.label = original

    def test_fallback_uses_class_name_only_not_module_path(self):
        """The fallback strictly uses `__name__`, never the dotted path."""
        # DefaultChatRunner.__name__ is "DefaultChatRunner"; the dotted path
        # in LLMRunner.name is much longer. The fallback should match __name__.
        original = DefaultChatRunner.label
        DefaultChatRunner.label = None
        try:
            result = _resolve_runner_label(DefaultChatRunner)
            self.assertNotIn(".", result)
            self.assertEqual(result, DefaultChatRunner.__name__)
        finally:
            DefaultChatRunner.label = original


class TestRunnerBlockSuccessPath(TestCase):
    def test_runner_block_emits_declared_label_description_default(self):
        """DefaultChatRunner declared label + description + default_model_metadata
        as part of F03-S01. The extractor emits all three on the runner block."""
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        payload = extract_topology(record)
        self.assertIsNone(payload["error"])

        runner = payload["runner"]
        self.assertIsNotNone(runner)
        self.assertEqual(runner["label"], DefaultChatRunner.label)
        self.assertEqual(runner["description"], DefaultChatRunner.description)
        self.assertEqual(runner["default_model"]["initializer_key"], "openai")
        self.assertEqual(runner["default_model"]["model_id"], "gpt-4o-mini")
        self.assertEqual(runner["default_model"]["params"], {"temperature": 0})
        self.assertIsNone(runner["default_model"]["override"])

    def test_runner_block_label_falls_back_to_class_name_when_unset(self):
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        original = DefaultChatRunner.label
        DefaultChatRunner.label = None
        try:
            payload = extract_topology(record)
        finally:
            DefaultChatRunner.label = original

        self.assertEqual(payload["runner"]["label"], "DefaultChatRunner")

    def test_runner_block_description_null_when_unset(self):
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        original = DefaultChatRunner.description
        DefaultChatRunner.description = None
        try:
            payload = extract_topology(record)
        finally:
            DefaultChatRunner.description = original

        self.assertIsNone(payload["runner"]["description"])

    def test_runner_block_default_model_nulls_when_metadata_unset(self):
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        original = DefaultChatRunner.default_model_metadata
        DefaultChatRunner.default_model_metadata = None
        try:
            payload = extract_topology(record)
        finally:
            DefaultChatRunner.default_model_metadata = original

        runner = payload["runner"]
        self.assertIsNone(runner["default_model"]["initializer_key"])
        self.assertIsNone(runner["default_model"]["model_id"])
        self.assertEqual(runner["default_model"]["params"], {})


class TestRunnerBlockOverride(TestCase):
    def test_runner_level_override_in_catalog_emits_full_block(self):
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
            params={"temperature": 0.3},
        )

        payload = extract_topology(record)
        override = payload["runner"]["default_model"]["override"]

        self.assertEqual(override["initializer_key"], "anthropic")
        self.assertEqual(override["model_id"], "claude-sonnet-4-6")
        self.assertEqual(override["params"], {"temperature": 0.3})
        self.assertTrue(override["in_catalog"])
        self.assertIsInstance(override["saved_at"], str)

    def test_runner_level_override_out_of_catalog_flags_in_catalog_false(self):
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-not-in-catalog",
        )

        payload = extract_topology(record)
        override = payload["runner"]["default_model"]["override"]

        self.assertFalse(override["in_catalog"])

    def test_no_runner_level_override_yields_null_override(self):
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        payload = extract_topology(record)
        self.assertIsNone(payload["runner"]["default_model"]["override"])

    def test_code_default_unchanged_when_override_exists(self):
        """The override does NOT mutate the code-declared default fields —
        admins see both rungs side by side in the payload."""
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )

        payload = extract_topology(record)
        runner = payload["runner"]

        # Code default fields unchanged by the override.
        self.assertEqual(runner["default_model"]["initializer_key"], "openai")
        self.assertEqual(runner["default_model"]["model_id"], "gpt-4o-mini")
        # Override block also populated.
        self.assertEqual(runner["default_model"]["override"]["initializer_key"], "anthropic")


class TestRunnerBlockErrorPayload(TestCase):
    def test_error_payload_sets_runner_to_null(self):
        """Unregistered runner → `runner_unregistered` error → `runner: null`."""
        record = LLMRunnerFactory(name="not.a.real.module.path.NoSuchRunner")
        payload = extract_topology(record)
        self.assertIsNotNone(payload["error"])
        self.assertEqual(payload["error"]["code"], "runner_unregistered")
        self.assertIsNone(payload["runner"])


class TestNoInitializerCalledForRunnerLevelRung(TestCase):
    """Rule 10 of the working doc: extractor must NOT invoke any initializer
    while building the runner block — same guarantee F02-S02 has for per-node."""

    def test_no_initialize_call_for_runner_level_override(self):
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )

        with patch(
            "baseapp_ai_langkit.runners.model_initializers.anthropic"
            ".AnthropicInitializer.initialize"
        ) as mock_initialize, patch(
            "baseapp_ai_langkit.runners.model_initializers.openai" ".OpenAIInitializer.initialize"
        ) as mock_openai_initialize:
            payload = extract_topology(record)

        self.assertIsNone(payload["error"])
        mock_initialize.assert_not_called()
        mock_openai_initialize.assert_not_called()
