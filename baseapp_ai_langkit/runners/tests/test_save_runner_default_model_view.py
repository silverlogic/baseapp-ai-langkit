"""Tests for the F03-S01 runner-level default-model save endpoint.

`POST/DELETE <pk>/topology/default-model/` upserts / clears
`LLMRunnerDefaultModelOverride`. Mirrors `test_model_save_view.py` one rung
higher — same staff gate, same CSRF, same structured error envelope, same
error codes; no `node_key` in the URL.
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerDefaultModelOverride,
)

CATALOG_INITIALIZER = "openai"
CATALOG_MODEL_ID = "gpt-4o-mini"  # seeded by migration 0003


class _RunnerDefaultModelSaveViewBase(TestCase):
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

    def _save_url(self, pk):
        return reverse(
            "admin:baseapp_ai_langkit_runners_llmrunner_save_runner_default_model",
            args=[pk],
        )

    def _staff_client(self, enforce_csrf_checks=False):
        client = Client(enforce_csrf_checks=enforce_csrf_checks)
        client.login(username="staff", password="x")
        return client

    def _non_staff_client(self):
        client = Client()
        client.login(username="not-staff", password="x")
        return client

    def _post(self, client, url, body):
        return client.post(url, data=json.dumps(body), content_type="application/json")


class TestRunnerDefaultModelSaveHappyPath(_RunnerDefaultModelSaveViewBase):
    def test_valid_save_creates_runner_level_override(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 0.3},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["override"]["initializer_key"], CATALOG_INITIALIZER)
        self.assertEqual(body["override"]["model_id"], CATALOG_MODEL_ID)
        self.assertEqual(body["override"]["params"], {"temperature": 0.3})
        self.assertTrue(body["override"]["in_catalog"])
        self.assertIsInstance(body["override"]["saved_at"], str)

        override = LLMRunnerDefaultModelOverride.objects.get(runner=record)
        self.assertEqual(override.initializer_key, CATALOG_INITIALIZER)
        self.assertEqual(override.params, {"temperature": 0.3})

    def test_repeat_save_updates_existing_row_in_place(self):
        record = self._runner_record()
        client = self._staff_client()
        first = self._post(
            client,
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 0.1},
            },
        )
        self.assertEqual(first.status_code, 200)
        second = self._post(
            client,
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 0.9},
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.filter(runner=record).count(), 1)
        override = LLMRunnerDefaultModelOverride.objects.get(runner=record)
        self.assertEqual(override.params, {"temperature": 0.9})


class TestRunnerDefaultModelSaveValidation(_RunnerDefaultModelSaveViewBase):
    def test_unknown_initializer_returns_initializer_unknown(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": "not-a-real-initializer",
                "model_id": "anything",
                "params": {},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "initializer_unknown")
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)

    def test_out_of_catalog_model_returns_model_not_in_catalog(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": "anthropic",
                "model_id": "claude-not-in-catalog",
                "params": {},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "model_not_in_catalog")
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)

    def test_disallowed_param_returns_param_not_allowed(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 0.5, "foo": "bar"},
            },
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "param_not_allowed")
        self.assertEqual(body["error"]["details"]["disallowed"], ["foo"])
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)

    def test_out_of_range_temperature_returns_param_invalid(self):
        record = self._runner_record()
        # Temperature range is 0.0–1.0; 3.5 is out of range → param_invalid.
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 3.5},
            },
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "param_invalid")
        self.assertIn("temperature", body["error"]["details"]["invalid"])

    def test_temperature_above_one_returns_param_invalid(self):
        """Boundary: 1.0 is valid, 1.5 is not (range is 0.0–1.0)."""
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {"temperature": 1.5},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "param_invalid")

    def test_missing_initializer_key_returns_validation_error(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {"model_id": CATALOG_MODEL_ID, "params": {}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_missing_model_id_returns_validation_error(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {"initializer_key": CATALOG_INITIALIZER, "params": {}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_params_not_a_dict_returns_validation_error(self):
        record = self._runner_record()
        response = self._post(
            self._staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": "not-an-object",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_malformed_json_body_returns_validation_error(self):
        record = self._runner_record()
        response = self._staff_client().post(
            self._save_url(record.pk),
            data="{not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_body_not_an_object_returns_validation_error(self):
        record = self._runner_record()
        response = self._staff_client().post(
            self._save_url(record.pk),
            data="[1, 2, 3]",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")


class TestRunnerDefaultModelSaveAuthorization(_RunnerDefaultModelSaveViewBase):
    def test_non_staff_user_is_rejected(self):
        record = self._runner_record()
        response = self._post(
            self._non_staff_client(),
            self._save_url(record.pk),
            {
                "initializer_key": CATALOG_INITIALIZER,
                "model_id": CATALOG_MODEL_ID,
                "params": {},
            },
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)

    def test_csrf_required(self):
        record = self._runner_record()
        client = self._staff_client(enforce_csrf_checks=True)
        response = client.post(
            self._save_url(record.pk),
            data=json.dumps(
                {
                    "initializer_key": CATALOG_INITIALIZER,
                    "model_id": CATALOG_MODEL_ID,
                    "params": {},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)


class TestRunnerDefaultModelSaveMethodGuard(_RunnerDefaultModelSaveViewBase):
    def test_get_returns_method_not_allowed_with_post_and_delete(self):
        record = self._runner_record()
        response = self._staff_client().get(self._save_url(record.pk))
        self.assertEqual(response.status_code, 405)
        allow = response.headers.get("Allow", "")
        self.assertIn("POST", allow)
        self.assertIn("DELETE", allow)

    def test_put_returns_method_not_allowed(self):
        record = self._runner_record()
        response = self._staff_client().put(self._save_url(record.pk))
        self.assertEqual(response.status_code, 405)


class TestRunnerDefaultModelReset(_RunnerDefaultModelSaveViewBase):
    """DELETE on the runner-level URL clears the override (idempotent)."""

    def _seed_override(self, record):
        return LLMRunnerDefaultModelOverride.objects.create(
            runner=record,
            initializer_key=CATALOG_INITIALIZER,
            model_id=CATALOG_MODEL_ID,
            params={"temperature": 0.5},
        )

    def test_delete_clears_existing_override(self):
        record = self._runner_record()
        self._seed_override(record)
        response = self._staff_client().delete(self._save_url(record.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"override": None})
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 0)

    def test_delete_is_idempotent_when_no_override_exists(self):
        record = self._runner_record()
        response = self._staff_client().delete(self._save_url(record.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"override": None})

    def test_delete_rejects_non_staff(self):
        record = self._runner_record()
        self._seed_override(record)
        response = self._non_staff_client().delete(self._save_url(record.pk))
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(LLMRunnerDefaultModelOverride.objects.count(), 1)
