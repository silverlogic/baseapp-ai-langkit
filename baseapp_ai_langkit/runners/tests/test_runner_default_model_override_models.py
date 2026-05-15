"""Tests for the F03-S01 `LLMRunnerDefaultModelOverride` model.

OneToOne invariant + catalog-deletion non-cascade + the related_name the
extractor and runtime helpers rely on.
"""

from django.db import IntegrityError
from django.test import TestCase

from baseapp_ai_langkit.runners.models import LLMRunnerDefaultModelOverride
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
    LLMRunnerDefaultModelOverrideFactory,
    LLMRunnerFactory,
)


class TestLLMRunnerDefaultModelOverride(TestCase):
    def test_one_to_one_constraint(self):
        """At most one runner-level override per runner (OneToOne FK)."""
        runner = LLMRunnerFactory()
        LLMRunnerDefaultModelOverrideFactory(runner=runner)
        with self.assertRaises(IntegrityError):
            LLMRunnerDefaultModelOverrideFactory(runner=runner)

    def test_no_fk_to_available_llm_model(self):
        """Override survives catalog deletion — there is no FK back to AvailableLLMModel."""
        catalog_row = AvailableLLMModelFactory(
            initializer_key="anthropic", model_id="claude-sonnet-4-6"
        )
        runner = LLMRunnerFactory()
        override = LLMRunnerDefaultModelOverrideFactory(
            runner=runner,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        catalog_row.delete()
        self.assertTrue(LLMRunnerDefaultModelOverride.objects.filter(pk=override.pk).exists())

    def test_related_name_default_model_override(self):
        """The OneToOne uses `related_name='default_model_override'` — the
        extractor's `_read_runner_default_override` and the runtime helper
        `_build_runner_default_llm` both rely on this exact name.
        """
        runner = LLMRunnerFactory()
        override = LLMRunnerDefaultModelOverrideFactory(runner=runner)
        self.assertEqual(runner.default_model_override.pk, override.pk)

    def test_str_repr_uses_runner_name_and_initializer_and_model(self):
        runner = LLMRunnerFactory(name="pkg.app.MyRunner")
        override = LLMRunnerDefaultModelOverrideFactory(
            runner=runner,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )
        rendered = str(override)
        self.assertIn("pkg.app.MyRunner", rendered)
        self.assertIn("default", rendered)
        self.assertIn("anthropic:claude-sonnet-4-6", rendered)

    def test_params_defaults_to_empty_dict(self):
        runner = LLMRunnerFactory()
        override = LLMRunnerDefaultModelOverride.objects.create(
            runner=runner,
            initializer_key="openai",
            model_id="gpt-4o-mini",
        )
        self.assertEqual(override.params, {})

    def test_cascade_on_runner_delete(self):
        """Deleting the parent LLMRunner deletes its default-model override."""
        runner = LLMRunnerFactory()
        override = LLMRunnerDefaultModelOverrideFactory(runner=runner)
        override_pk = override.pk
        runner.delete()
        self.assertFalse(LLMRunnerDefaultModelOverride.objects.filter(pk=override_pk).exists())
