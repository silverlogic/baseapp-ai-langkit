"""Tests for the F02-S02 Django system check that warns when a registered Runner
has no `default_model_metadata` declared.

The check is a `Warning` (not an `Error`) so existing consumer projects on upgrade
see the message but aren't blocked from deploying.
"""

from unittest.mock import patch

from django.core.checks import Warning
from django.test import SimpleTestCase

from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.checks import (
    check_runners_have_default_model_metadata,
)


class _RunnerWithoutDefault(BaseRunnerInterface):
    """Test runner that intentionally does NOT declare default_model_metadata."""

    def run(self):
        return ""

    @classmethod
    def get_workflow_class(cls):
        raise NotImplementedError


class _RunnerWithDefault(BaseRunnerInterface):
    default_model_metadata = LLMModelMetadata(
        initializer_key="openai",
        model_id="gpt-4o-mini",
        params={"temperature": 0},
    )

    def run(self):
        return ""

    @classmethod
    def get_workflow_class(cls):
        raise NotImplementedError


class TestDefaultModelMetadataCheck(SimpleTestCase):
    def test_warning_emitted_for_runner_missing_default(self):
        with patch(
            "baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all",
            return_value=[_RunnerWithoutDefault],
        ):
            warnings = check_runners_have_default_model_metadata(app_configs=None)
        self.assertEqual(len(warnings), 1)
        warning = warnings[0]
        self.assertIsInstance(warning, Warning)
        self.assertEqual(warning.id, "baseapp_ai_langkit_runners.W001")
        self.assertIn("_RunnerWithoutDefault", warning.msg)

    def test_no_warning_for_runner_with_default(self):
        with patch(
            "baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all",
            return_value=[_RunnerWithDefault],
        ):
            warnings = check_runners_have_default_model_metadata(app_configs=None)
        self.assertEqual(warnings, [])

    def test_langkit_default_runner_does_not_trigger_warning(self):
        """The langkit-shipped DefaultChatRunner DID declare default_model_metadata
        in this change — it must NOT trigger the warning when the real registry is used."""
        warnings = check_runners_have_default_model_metadata(app_configs=None)
        runner_id = f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        for w in warnings:
            self.assertNotIn(runner_id, w.msg)
