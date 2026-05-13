"""Tests for the F02-S01 topology-layout save endpoint.

POST `<pk>/topology/layout/` upserts `LLMRunnerTopologyLayout.node_positions`
for a runner; empty `node_positions` clears the row (Reset-to-auto). The
extractor surfaces those positions as `position` on each node in the topology
payload so the widget can short-circuit dagre.
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.models import LLMRunner, LLMRunnerTopologyLayout
from baseapp_ai_langkit.runners.topology.extractor import extract_topology


class _LayoutViewBaseTest(TestCase):
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

    def _layout_url(self, pk):
        return reverse(
            "admin:baseapp_ai_langkit_runners_llmrunner_save_topology_layout",
            args=[pk],
        )

    def _staff_client(self, enforce_csrf_checks=False):
        c = Client(enforce_csrf_checks=enforce_csrf_checks)
        c.login(username="staff", password="x")
        return c

    def _non_staff_client(self):
        c = Client()
        c.login(username="not-staff", password="x")
        return c

    def _post(self, client, url, payload):
        return client.post(url, data=json.dumps(payload), content_type="application/json")


class TestSaveTopologyLayoutHappyPath(_LayoutViewBaseTest):
    def test_first_save_creates_row_and_returns_layout(self):
        record = self._runner_record()
        body = {
            "node_positions": {
                "general_llm": {"x": 100, "y": 200},
            }
        }
        response = self._post(self._staff_client(), self._layout_url(record.pk), body)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["layout"]["node_positions"], {"general_llm": {"x": 100.0, "y": 200.0}}
        )
        self.assertIsInstance(data["layout"]["saved_at"], str)

        row = LLMRunnerTopologyLayout.objects.get(runner=record)
        self.assertEqual(row.node_positions, {"general_llm": {"x": 100.0, "y": 200.0}})

    def test_repeat_save_overwrites_existing_row(self):
        record = self._runner_record()
        client = self._staff_client()
        self._post(
            client,
            self._layout_url(record.pk),
            {"node_positions": {"general_llm": {"x": 1, "y": 2}}},
        )
        # New save with different keys replaces the prior content wholesale.
        self._post(
            client, self._layout_url(record.pk), {"node_positions": {"other": {"x": 5, "y": 5}}}
        )
        row = LLMRunnerTopologyLayout.objects.get(runner=record)
        self.assertEqual(row.node_positions, {"other": {"x": 5.0, "y": 5.0}})

    def test_empty_node_positions_resets_the_layout(self):
        record = self._runner_record()
        client = self._staff_client()
        self._post(
            client,
            self._layout_url(record.pk),
            {"node_positions": {"general_llm": {"x": 10, "y": 20}}},
        )
        response = self._post(client, self._layout_url(record.pk), {"node_positions": {}})
        self.assertEqual(response.status_code, 200)
        row = LLMRunnerTopologyLayout.objects.get(runner=record)
        self.assertEqual(row.node_positions, {})


class TestSaveTopologyLayoutValidationErrors(_LayoutViewBaseTest):
    def test_missing_node_positions_key_returns_400(self):
        record = self._runner_record()
        response = self._post(self._staff_client(), self._layout_url(record.pk), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_node_positions_must_be_object(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._layout_url(record.pk),
            {"node_positions": [["x", 1]]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_position_entries_must_have_numeric_x_and_y(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._layout_url(record.pk),
            {"node_positions": {"n": {"x": "not-a-number", "y": 0}}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_malformed_json_returns_400(self):
        record = self._runner_record()
        response = self._staff_client().post(
            self._layout_url(record.pk),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_non_post_returns_405(self):
        record = self._runner_record()
        response = self._staff_client().get(self._layout_url(record.pk))
        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response["Allow"])


class TestSaveTopologyLayoutAuth(_LayoutViewBaseTest):
    def test_non_staff_user_rejected_no_row_written(self):
        record = self._runner_record()
        response = self._post(
            self._non_staff_client(),
            self._layout_url(record.pk),
            {"node_positions": {"n": {"x": 1, "y": 2}}},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertFalse(LLMRunnerTopologyLayout.objects.filter(runner=record).exists())

    def test_anonymous_rejected(self):
        record = self._runner_record()
        response = Client().post(
            self._layout_url(record.pk),
            data=json.dumps({"node_positions": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])

    def test_csrf_token_required(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(enforce_csrf_checks=True),
            self._layout_url(record.pk),
            {"node_positions": {"n": {"x": 0, "y": 0}}},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LLMRunnerTopologyLayout.objects.filter(runner=record).exists())


class TestTopologyReflectsPersistedLayout(_LayoutViewBaseTest):
    def test_topology_payload_carries_persisted_positions(self):
        record = self._runner_record()
        # Save a position for the only declared node on DefaultChatRunner.
        self._post(
            self._staff_client(),
            self._layout_url(record.pk),
            {"node_positions": {"general_llm": {"x": 99, "y": 42}}},
        )
        payload = extract_topology(record)
        self.assertIsNone(payload["error"])
        node = next(n for n in payload["nodes"] if n["key"] == "general_llm")
        self.assertEqual(node["position"], {"x": 99.0, "y": 42.0})

    def test_topology_payload_position_is_null_when_no_layout_row(self):
        record = self._runner_record()
        payload = extract_topology(record)
        node = next(n for n in payload["nodes"] if n["key"] == "general_llm")
        self.assertIsNone(node["position"])

    def test_topology_payload_position_is_null_for_unsaved_keys(self):
        # Layout row exists but doesn't list this particular node — still None.
        record = self._runner_record()
        self._post(
            self._staff_client(),
            self._layout_url(record.pk),
            {"node_positions": {"different_node": {"x": 0, "y": 0}}},
        )
        payload = extract_topology(record)
        node = next(n for n in payload["nodes"] if n["key"] == "general_llm")
        self.assertIsNone(node["position"])
