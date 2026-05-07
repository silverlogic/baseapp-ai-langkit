from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.models import LLMRunner


class _BaseTopologyViewTest(TestCase):
    def _runner_record(self):
        record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )
        return record

    def _topology_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_topology", args=[pk])


class TestTopologyViewAuth(_BaseTopologyViewTest):
    def test_anonymous_user_is_redirected_to_login(self):
        record = self._runner_record()
        client = Client()
        response = client.get(self._topology_url(record.pk))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])

    def test_non_staff_user_is_redirected_to_login(self):
        record = self._runner_record()
        User = get_user_model()
        User.objects.create_user(username="not-staff", password="x", is_staff=False)
        client = Client()
        client.login(username="not-staff", password="x")
        response = client.get(self._topology_url(record.pk))
        # admin_view redirects non-staff to admin login (302), no payload leaked.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertNotIn(b"nodes", response.content)

    def test_staff_user_gets_200_with_payload(self):
        record = self._runner_record()
        User = get_user_model()
        User.objects.create_user(username="staff", password="x", is_staff=True)
        client = Client()
        client.login(username="staff", password="x")
        response = client.get(self._topology_url(record.pk))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("nodes", body)
        self.assertIn("edges", body)
        self.assertIn("error", body)


class TestTopologyViewAlwaysReturns200(_BaseTopologyViewTest):
    """The view never 5xxs on extraction failure — it always returns 200 with
    a structured error payload. Routing 404 is the only non-200 path (and 302
    for unauthenticated requests handled by `admin_view`).
    """

    def setUp(self):
        User = get_user_model()
        User.objects.create_user(username="staff", password="x", is_staff=True)
        self.client = Client()
        self.client.login(username="staff", password="x")

    def test_unknown_runner_pk_returns_404_routing(self):
        url = self._topology_url(999_999)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_runner_unregistered_returns_200_with_error_code(self):
        # Create an LLMRunner row whose name is NOT in the registry.
        unregistered = LLMRunner.objects.create(name="some.unknown.module.GhostRunner")
        response = self.client.get(self._topology_url(unregistered.pk))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["error"]["code"], "runner_unregistered")
        self.assertEqual(body["nodes"], [])
        self.assertEqual(body["edges"], [])

    def test_workflow_init_failure_returns_200_with_error_code(self):
        record = self._runner_record()
        with patch.object(
            DefaultChatRunner,
            "build_topology_workflow",
            classmethod(lambda cls, **kw: (_ for _ in ()).throw(RuntimeError("init fail"))),
        ):
            response = self.client.get(self._topology_url(record.pk))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["error"]["code"], "workflow_init_failed")

    def test_topology_builder_not_declared_returns_200_with_error_code(self):
        record = self._runner_record()
        with patch.object(
            DefaultChatRunner,
            "build_topology_workflow",
            classmethod(lambda cls, **kw: (_ for _ in ()).throw(NotImplementedError("no builder"))),
        ):
            response = self.client.get(self._topology_url(record.pk))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["error"]["code"], "topology_builder_not_declared")
