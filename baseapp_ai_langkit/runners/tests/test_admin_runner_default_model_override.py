"""Tests for the F03-S01 admin surfaces.

The override models (`LLMRunnerNodeModelOverride`, `LLMRunnerDefaultModelOverride`)
are intentionally NOT registered as standalone admin classes — override editing
is exclusive to the React Flow modal. This file tests the surviving admin
surface: the `LLMRunnerAdmin.runner_label` accessor that drives the changelist's
primary column.
"""

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.admin import LLMRunnerAdmin
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerDefaultModelOverride,
    LLMRunnerNodeModelOverride,
)


class TestOverrideModelsNotRegistered(TestCase):
    """Both override models stay out of Django admin so admins aren't tempted
    to edit overrides from two surfaces. Editing happens only in the React
    Flow modal (per-node sidebar Edit button + runner-level banner button)."""

    def test_per_node_override_model_is_not_registered(self):
        self.assertNotIn(LLMRunnerNodeModelOverride, admin.site._registry)

    def test_runner_default_override_model_is_not_registered(self):
        self.assertNotIn(LLMRunnerDefaultModelOverride, admin.site._registry)


class TestLLMRunnerAdminLabelColumn(TestCase):
    """The list_display promotion adds a `runner_label` accessor as the
    primary column. The accessor delegates to `_resolve_runner_label` and
    falls back to `obj.name` for orphan rows."""

    def setUp(self):
        self.admin_site = AdminSite()
        self.admin = LLMRunnerAdmin(LLMRunner, self.admin_site)

    def test_list_display_starts_with_runner_label(self):
        self.assertEqual(self.admin.list_display, ("runner_label", "name"))

    def test_runner_label_returns_declared_label_when_set(self):
        record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        # DefaultChatRunner declares `label = "Default chat"` in F03-S01.
        self.assertEqual(self.admin.runner_label(record), DefaultChatRunner.label)

    def test_runner_label_falls_back_to_class_name_when_label_is_none(self):
        record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        original = DefaultChatRunner.label
        DefaultChatRunner.label = None
        try:
            label = self.admin.runner_label(record)
        finally:
            DefaultChatRunner.label = original

        self.assertEqual(label, "DefaultChatRunner")

    def test_runner_label_falls_back_to_dotted_name_for_orphan_row(self):
        """When `obj.runner_class` raises (no class in registry), accessor
        falls back to `obj.name` so the list view never blank-renders."""
        orphan = LLMRunner.objects.create(name="not.a.real.module.path.NoSuchRunnerClass")
        self.assertEqual(self.admin.runner_label(orphan), orphan.name)
