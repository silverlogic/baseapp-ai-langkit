"""Tests for the F02-S02 `AvailableLLMModel` and `LLMRunnerNodeModelOverride` models.

Includes uniqueness, OneToOne, and seed-row presence after the 0003 migration.
"""

from django.db import IntegrityError
from django.test import TestCase

from baseapp_ai_langkit.runners.models import (
    AvailableLLMModel,
    LLMRunnerNodeModelOverride,
)
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeModelOverrideFactory,
)


class TestAvailableLLMModel(TestCase):
    def test_unique_together_blocks_duplicate_initializer_key_and_model_id(self):
        # Use the model API directly (the factory has `django_get_or_create` and
        # would silently upsert, hiding the constraint).
        AvailableLLMModel.objects.create(
            label="First", initializer_key="anthropic", model_id="claude-sonnet-4-6"
        )
        with self.assertRaises(IntegrityError):
            AvailableLLMModel.objects.create(
                label="Second",
                initializer_key="anthropic",
                model_id="claude-sonnet-4-6",
            )

    def test_seed_row_exists_after_migration(self):
        """The 0003 migration seeds the catalog with one openai:gpt-4o-mini row."""
        seed = AvailableLLMModel.objects.filter(
            initializer_key="openai", model_id="gpt-4o-mini"
        ).first()
        self.assertIsNotNone(seed)
        self.assertEqual(seed.label, "GPT-4o mini")
        self.assertEqual(seed.default_params, {"temperature": 0})

    def test_str_repr_is_label_plus_initializer_and_model(self):
        row = AvailableLLMModelFactory(
            label="Claude Sonnet 4.6",
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        self.assertEqual(str(row), "Claude Sonnet 4.6 (anthropic:claude-sonnet-4-6)")

    def test_default_params_defaults_to_empty_dict(self):
        row = AvailableLLMModel.objects.create(
            label="Test",
            initializer_key="generic",
            model_id="some/model",
        )
        self.assertEqual(row.default_params, {})


class TestLLMRunnerNodeModelOverride(TestCase):
    def test_one_to_one_constraint(self):
        """At most one override per node (the OneToOne FK)."""
        node = LLMRunnerNodeFactory()
        LLMRunnerNodeModelOverrideFactory(runner_node=node)
        with self.assertRaises(IntegrityError):
            LLMRunnerNodeModelOverrideFactory(runner_node=node)

    def test_no_fk_to_available_llm_model(self):
        """Override survives catalog deletion — there's no FK back to AvailableLLMModel."""
        catalog_row = AvailableLLMModelFactory(
            initializer_key="anthropic", model_id="claude-sonnet-4-6"
        )
        node = LLMRunnerNodeFactory()
        override = LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        catalog_row.delete()
        # Override row is untouched.
        self.assertTrue(LLMRunnerNodeModelOverride.objects.filter(pk=override.pk).exists())

    def test_str_repr_uses_runner_node_and_initializer_and_model(self):
        node = LLMRunnerNodeFactory(node="summarizer")
        override = LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        self.assertIn("summarizer", str(override))
        self.assertIn("anthropic:claude-sonnet-4-6", str(override))

    def test_params_defaults_to_empty_dict(self):
        node = LLMRunnerNodeFactory()
        override = LLMRunnerNodeModelOverride.objects.create(
            runner_node=node,
            initializer_key="openai",
            model_id="gpt-4o-mini",
        )
        self.assertEqual(override.params, {})
