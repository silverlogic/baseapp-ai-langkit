"""Tests for the F02-S01 prompt-save endpoints.

The endpoints persist usage_prompt / state_modifier overrides through the
existing `LLMRunnerNodeUsagePrompt` and `LLMRunnerNodeStateModifier` models,
relying on `full_clean()` so validation parity with the legacy nested-inline
editor is preserved.

Schemas on `MessagesWorker` are class-level-patched for the test class so
`DefaultChatRunner.get_available_nodes()["general_llm"]` has predictable
`required_placeholders` to exercise the validation path against.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
)
from baseapp_ai_langkit.runners.topology.extractor import extract_topology


# Bare placeholder names — the codebase convention. `BasePromptSchema.validate`
# checks for the format-string token `{name}` in the prompt; storing the bare
# name in `required_placeholders` is what every real schema does
# (`available_nodes_list`, `slack_context`, etc.).
USAGE_PROMPT_REQUIRED = "topic"
USAGE_PROMPT_TOKEN = "{" + USAGE_PROMPT_REQUIRED + "}"
USAGE_PROMPT_DEFAULT = f"Default usage prompt referencing {USAGE_PROMPT_TOKEN}."
STATE_MODIFIER_REQUIRED = "tone"
STATE_MODIFIER_TOKEN = "{" + STATE_MODIFIER_REQUIRED + "}"
STATE_MODIFIER_DEFAULT = (
    f"Default state modifier referencing {STATE_MODIFIER_TOKEN}."
)


def _patched_usage_prompt_schema():
    return BasePromptSchema(
        description="Test usage prompt for F02-S01",
        prompt=USAGE_PROMPT_DEFAULT,
        required_placeholders=[USAGE_PROMPT_REQUIRED],
    )


def _patched_state_modifier_schema():
    return BasePromptSchema(
        description="Test state modifier for F02-S01",
        prompt=STATE_MODIFIER_DEFAULT,
        required_placeholders=[STATE_MODIFIER_REQUIRED],
    )


class _SaveViewBaseTest(TestCase):
    """Shared fixtures for the prompt-save endpoint tests.

    Patches `MessagesWorker.usage_prompt_schema` and `state_modifier_schema`
    at class scope so `DefaultChatRunner`'s `general_llm` node has stable,
    placeholder-bearing schemas for every test in subclasses.
    """

    NODE_KEY = "general_llm"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._patches = [
            patch.object(
                MessagesWorker, "usage_prompt_schema", new=_patched_usage_prompt_schema()
            ),
            patch.object(
                MessagesWorker, "state_modifier_schema", new=_patched_state_modifier_schema()
            ),
        ]
        for p in cls._patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls._patches:
            p.stop()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff_user = User.objects.create_user(
            username="staff", password="x", is_staff=True, is_superuser=True
        )
        cls.non_staff_user = User.objects.create_user(
            username="not-staff", password="x", is_staff=False
        )

    def _runner_record(self):
        record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        return record

    def _usage_prompt_url(self, pk, node_key=None):
        return reverse(
            "admin:baseapp_ai_langkit_runners_llmrunner_save_usage_prompt",
            args=[pk, node_key or self.NODE_KEY],
        )

    def _state_modifier_url(self, pk, node_key=None, index=0):
        return reverse(
            "admin:baseapp_ai_langkit_runners_llmrunner_save_state_modifier",
            args=[pk, node_key or self.NODE_KEY, index],
        )

    def _topology_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_topology", args=[pk])

    def _legacy_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_change_legacy", args=[pk])

    def _staff_client(self, enforce_csrf_checks=False):
        client = Client(enforce_csrf_checks=enforce_csrf_checks)
        client.login(username="staff", password="x")
        return client

    def _non_staff_client(self):
        client = Client()
        client.login(username="not-staff", password="x")
        return client

    def _post(self, client, url, text):
        return client.post(url, data=json.dumps({"text": text}), content_type="application/json")


class TestSaveUsagePromptHappyPath(_SaveViewBaseTest):
    def test_first_save_creates_row_and_returns_override(self):
        """4.1.1 — Staff POST creates `LLMRunnerNodeUsagePrompt` and returns 200 with {override}."""
        record = self._runner_record()
        valid_text = f"Custom usage prompt with {USAGE_PROMPT_TOKEN}."

        response = self._post(self._staff_client(), self._usage_prompt_url(record.pk), valid_text)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["override"]["text"], valid_text)
        self.assertIsInstance(body["override"]["saved_at"], str)
        self.assertTrue(body["override"]["saved_at"])
        # DB upsert: exactly one row attached to the runner node.
        node = LLMRunnerNode.objects.get(runner=record, node=self.NODE_KEY)
        usage_prompt = LLMRunnerNodeUsagePrompt.objects.get(runner_node=node)
        self.assertEqual(usage_prompt.usage_prompt, valid_text)

    def test_repeat_save_updates_existing_row_in_place(self):
        """4.1.2 — second save to the same target updates the same row."""
        record = self._runner_record()
        first_text = f"First {USAGE_PROMPT_TOKEN}."
        second_text = f"Second {USAGE_PROMPT_TOKEN}."

        client = self._staff_client()
        self._post(client, self._usage_prompt_url(record.pk), first_text)
        response = self._post(client, self._usage_prompt_url(record.pk), second_text)

        self.assertEqual(response.status_code, 200)
        node = LLMRunnerNode.objects.get(runner=record, node=self.NODE_KEY)
        # Exactly one usage-prompt row per node (OneToOne) — the value updated.
        self.assertEqual(LLMRunnerNodeUsagePrompt.objects.filter(runner_node=node).count(), 1)
        self.assertEqual(
            LLMRunnerNodeUsagePrompt.objects.get(runner_node=node).usage_prompt, second_text
        )


class TestSaveStateModifierHappyPath(_SaveViewBaseTest):
    def test_first_save_creates_row_and_returns_override(self):
        """4.1.3 — Staff POST creates `LLMRunnerNodeStateModifier(index=0)` and returns 200."""
        record = self._runner_record()
        valid_text = f"Custom state modifier with {STATE_MODIFIER_TOKEN}."

        response = self._post(
            self._staff_client(), self._state_modifier_url(record.pk, index=0), valid_text
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["override"]["text"], valid_text)
        node = LLMRunnerNode.objects.get(runner=record, node=self.NODE_KEY)
        sm = LLMRunnerNodeStateModifier.objects.get(runner_node=node, index=0)
        self.assertEqual(sm.state_modifier, valid_text)


class TestValidationErrors(_SaveViewBaseTest):
    def test_missing_placeholder_returns_400_and_no_db_write(self):
        """4.1.4 — text missing a required placeholder → 400 missing_placeholders."""
        record = self._runner_record()
        bad_text = "This text has no placeholder."  # missing {topic}

        response = self._post(self._staff_client(), self._usage_prompt_url(record.pk), bad_text)

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "missing_placeholders")
        self.assertIn(USAGE_PROMPT_REQUIRED, body["error"]["details"]["missing"])
        # No row should have been created.
        self.assertFalse(
            LLMRunnerNodeUsagePrompt.objects.filter(
                runner_node__runner=record, runner_node__node=self.NODE_KEY
            ).exists()
        )

    def test_unknown_node_returns_404_node_unknown(self):
        """4.1.5 — `node_key` not in the runner's available nodes → 404 node_unknown."""
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._usage_prompt_url(record.pk, node_key="ghost-node"),
            f"Some text {USAGE_PROMPT_TOKEN}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "node_unknown")
        # No spurious LLMRunnerNode row for the ghost key.
        self.assertFalse(
            LLMRunnerNode.objects.filter(runner=record, node="ghost-node").exists()
        )

    def test_state_modifier_index_out_of_range_returns_404(self):
        """4.1.6 — index past `get_static_state_modifier_list()` length → 404."""
        record = self._runner_record()
        # MessagesWorker has exactly one state_modifier_schema after patching → indexes 0..0.
        response = self._post(
            self._staff_client(),
            self._state_modifier_url(record.pk, index=5),
            f"Some text {STATE_MODIFIER_TOKEN}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "state_modifier_index_out_of_range")
        self.assertFalse(
            LLMRunnerNodeStateModifier.objects.filter(
                runner_node__runner=record, runner_node__node=self.NODE_KEY, index=5
            ).exists()
        )

    def test_non_post_method_returns_405(self):
        """4.1.7 — GET / PUT / DELETE return 405 with Allow: POST."""
        record = self._runner_record()
        response = self._staff_client().get(self._usage_prompt_url(record.pk))

        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response["Allow"])

    def test_invalid_json_body_returns_400_validation_error(self):
        """Defensive: malformed JSON body falls under the validation_error code."""
        record = self._runner_record()
        response = self._staff_client().post(
            self._usage_prompt_url(record.pk),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_missing_text_field_returns_400_validation_error(self):
        """Defensive: JSON without a `text` string → validation_error."""
        record = self._runner_record()
        response = self._staff_client().post(
            self._usage_prompt_url(record.pk),
            data=json.dumps({"not_text": "value"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")


class TestSaveViewAuth(_SaveViewBaseTest):
    def test_non_staff_user_rejected_no_db_write(self):
        """4.1.8 — non-staff user gets admin's standard auth-failure (redirect to login)."""
        record = self._runner_record()
        response = self._post(
            self._non_staff_client(),
            self._usage_prompt_url(record.pk),
            f"text {USAGE_PROMPT_TOKEN}",
        )

        # admin_view sends non-staff to the admin login (302 → /login).
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertFalse(
            LLMRunnerNodeUsagePrompt.objects.filter(runner_node__runner=record).exists()
        )

    def test_anonymous_user_rejected_no_db_write(self):
        """4.1.9 — unauthenticated POST is redirected to the admin login."""
        record = self._runner_record()
        response = Client().post(
            self._usage_prompt_url(record.pk),
            data=json.dumps({"text": f"text {USAGE_PROMPT_TOKEN}"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertFalse(
            LLMRunnerNodeUsagePrompt.objects.filter(runner_node__runner=record).exists()
        )

    def test_post_without_csrf_token_returns_403(self):
        """4.1.10 — CSRF-enforced staff POST without the token returns 403, no write."""
        record = self._runner_record()
        response = self._post(
            self._staff_client(enforce_csrf_checks=True),
            self._usage_prompt_url(record.pk),
            f"text {USAGE_PROMPT_TOKEN}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            LLMRunnerNodeUsagePrompt.objects.filter(runner_node__runner=record).exists()
        )


class TestTopologyReflectsSavedOverride(_SaveViewBaseTest):
    def test_usage_prompt_override_visible_in_topology_payload(self):
        """4.1.11 (usage_prompt) — saved override is reflected in extract_topology."""
        record = self._runner_record()
        valid_text = f"After-save text {USAGE_PROMPT_TOKEN}."

        self._post(self._staff_client(), self._usage_prompt_url(record.pk), valid_text)

        payload = extract_topology(record)
        self.assertIsNone(payload["error"])
        node = next(n for n in payload["nodes"] if n["key"] == self.NODE_KEY)
        self.assertIsNotNone(node["usage_prompt"])
        self.assertEqual(node["usage_prompt"]["override"]["text"], valid_text)

    def test_state_modifier_override_visible_in_topology_payload(self):
        """4.1.11 (state_modifier) — saved override is reflected in extract_topology."""
        record = self._runner_record()
        valid_text = f"After-save state-mod {STATE_MODIFIER_TOKEN}."

        self._post(
            self._staff_client(), self._state_modifier_url(record.pk, index=0), valid_text
        )

        payload = extract_topology(record)
        self.assertIsNone(payload["error"])
        node = next(n for n in payload["nodes"] if n["key"] == self.NODE_KEY)
        state_modifier_entry = next(
            sm for sm in node["state_modifier_prompts"] if sm["key"] == "0"
        )
        self.assertEqual(state_modifier_entry["override"]["text"], valid_text)


class TestRestoreDefaultViaEmptyText(_SaveViewBaseTest):
    """Front-end "Restore default" support — POSTing an empty text clears the
    override path without a dedicated endpoint:

    * `clean_*` short-circuits on empty text (no validation runs)
    * the topology extractor's override readers treat empty text as `override: None`
    """

    def test_post_empty_text_clears_an_existing_usage_prompt_override(self):
        record = self._runner_record()
        client = self._staff_client()

        # Seed an override first.
        valid_text = f"My override referencing {USAGE_PROMPT_TOKEN}."
        self._post(client, self._usage_prompt_url(record.pk), valid_text)
        node = LLMRunnerNode.objects.get(runner=record, node=self.NODE_KEY)
        self.assertEqual(
            LLMRunnerNodeUsagePrompt.objects.get(runner_node=node).usage_prompt,
            valid_text,
        )

        # Restore: POST empty text. Same endpoint, same auth, no missing-placeholder
        # rejection (empty text short-circuits `clean_usage_prompt`).
        response = self._post(client, self._usage_prompt_url(record.pk), "")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["override"]["text"], "")

        # The row is now empty (logically equivalent to "no override").
        self.assertEqual(
            LLMRunnerNodeUsagePrompt.objects.get(runner_node=node).usage_prompt,
            "",
        )

        # Topology endpoint reports override: null — the sidebar will collapse
        # the override pane and show only the default.
        payload = extract_topology(record)
        node_payload = next(n for n in payload["nodes"] if n["key"] == self.NODE_KEY)
        self.assertIsNone(node_payload["usage_prompt"]["override"])

    def test_post_empty_text_clears_an_existing_state_modifier_override(self):
        record = self._runner_record()
        client = self._staff_client()

        valid_text = f"My override referencing {STATE_MODIFIER_TOKEN}."
        self._post(client, self._state_modifier_url(record.pk, index=0), valid_text)
        node = LLMRunnerNode.objects.get(runner=record, node=self.NODE_KEY)
        self.assertEqual(
            LLMRunnerNodeStateModifier.objects.get(runner_node=node, index=0).state_modifier,
            valid_text,
        )

        response = self._post(client, self._state_modifier_url(record.pk, index=0), "")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            LLMRunnerNodeStateModifier.objects.get(runner_node=node, index=0).state_modifier,
            "",
        )

        payload = extract_topology(record)
        node_payload = next(n for n in payload["nodes"] if n["key"] == self.NODE_KEY)
        sm_entry = next(
            sm for sm in node_payload["state_modifier_prompts"] if sm["key"] == "0"
        )
        self.assertIsNone(sm_entry["override"])


class TestLegacyEditorUnaffected(_SaveViewBaseTest):
    def test_legacy_change_view_still_renders(self):
        """4.1.12 — the legacy nested-inline editor at change/legacy/ is not regressed.

        F01's test_admin_change_view already covers the legacy URL's behaviors in
        depth; this is a regression guard that confirms S01 did not break the URL.
        """
        record = self._runner_record()
        response = self._staff_client().get(self._legacy_url(record.pk))
        self.assertEqual(response.status_code, 200)
        # The legacy page should *not* render the graph mount target.
        self.assertNotIn(b"runner-topology-root", response.content)
