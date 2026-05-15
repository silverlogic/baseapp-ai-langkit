"""Tests for the registry-backed `initializer_key` dropdown on the `AvailableLLMModel`
admin form.

The form swaps the raw `CharField` for a `ChoiceField` whose options come from
`LLMModelInitializerRegistry.get_all()`. Values not currently in the registry
remain editable so operators can correct an orphaned row rather than silently
losing the value. New forms default to the `"generic"` initializer.
"""

from django.test import TestCase

from baseapp_ai_langkit.runners.admin import AvailableLLMModelForm
from baseapp_ai_langkit.runners.models import AvailableLLMModel


class TestInitializerKeyDropdown(TestCase):
    def test_choices_come_from_the_registry(self):
        form = AvailableLLMModelForm()
        values = {key for key, _ in form.fields["initializer_key"].choices}
        # Built-ins shipped by langkit.
        for key in ("openai", "anthropic", "gemini", "openrouter", "generic"):
            self.assertIn(key, values)

    def test_choice_labels_include_label_and_key(self):
        form = AvailableLLMModelForm()
        labels = dict(form.fields["initializer_key"].choices)
        self.assertEqual(labels["openai"], "OpenAI (openai)")

    def test_form_rejects_unregistered_value_on_create(self):
        form = AvailableLLMModelForm(
            data={
                "label": "Bogus",
                "initializer_key": "not-a-real-initializer",
                "model_id": "x",
                "default_params": "{}",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("initializer_key", form.errors)

    def test_form_accepts_a_registered_value(self):
        form = AvailableLLMModelForm(
            data={
                "label": "Custom",
                "initializer_key": "openai",
                "model_id": "gpt-4o-mini-test",
                "default_params": "{}",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_existing_orphan_row_is_addressable(self):
        """An existing row whose `initializer_key` is no longer registered
        SHALL still be editable — the choice is appended with a "not
        registered" label so the admin sees and can correct it."""
        instance = AvailableLLMModel.objects.create(
            label="Orphan",
            initializer_key="legacy-removed",
            model_id="x",
        )
        form = AvailableLLMModelForm(instance=instance)
        values = {key for key, _ in form.fields["initializer_key"].choices}
        self.assertIn("legacy-removed", values)

    def test_new_form_defaults_to_generic_initializer(self):
        """A fresh add-form pre-selects 'generic' so admins land on a
        provider-agnostic initializer that accepts any (model_id) via
        LangChain's init_chat_model — no need to know which provider-specific
        initializer to pick first."""
        form = AvailableLLMModelForm()
        self.assertEqual(form.fields["initializer_key"].initial, "generic")

    def test_existing_row_does_not_force_generic_initial(self):
        """Editing an existing row uses the row's persisted `initializer_key`,
        NOT the generic default — the form's `initial` only applies to add
        forms."""
        instance = AvailableLLMModel.objects.create(
            label="Existing",
            initializer_key="openai",
            model_id="gpt-x",
        )
        form = AvailableLLMModelForm(instance=instance)
        # ChoiceField's `initial` is None on edit forms (the bound value comes
        # from the instance instead).
        self.assertIsNone(form.fields["initializer_key"].initial)
