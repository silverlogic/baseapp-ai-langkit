import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from baseapp_ai_langkit import __version__
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.admin import LLMRunnerAdmin
from baseapp_ai_langkit.runners.models import LLMRunner

GRAPH_MOUNT_TARGET = '<div id="runner-topology-root"'
GRAPH_MOUNT_CALL = "RunnerTopologyWidget.mount("


class _BaseLLMRunnerAdminTest(TestCase):
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

    def _change_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_change", args=[pk])

    def _legacy_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_change_legacy", args=[pk])

    def _topology_url(self, pk):
        return reverse("admin:baseapp_ai_langkit_runners_llmrunner_topology", args=[pk])

    def _staff_client(self):
        client = Client()
        client.login(username="staff", password="x")
        return client

    def _non_staff_client(self):
        client = Client()
        client.login(username="not-staff", password="x")
        return client


class TestGraphView(_BaseLLMRunnerAdminTest):
    def test_staff_get_renders_graph_with_mount_call_and_reversed_urls(self):
        record = self._runner_record()
        response = self._staff_client().get(self._change_url(record.pk))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(GRAPH_MOUNT_TARGET, body)
        self.assertIn(GRAPH_MOUNT_CALL, body)
        self.assertIn(self._topology_url(record.pk), body)
        self.assertIn(self._legacy_url(record.pk), body)
        self.assertIn(f"runner_topology_widget.js?v={__version__}", body)
        self.assertIn(f"runner_topology_widget.css?v={__version__}", body)

    def test_no_third_party_cdn_urls_in_graph_page(self):
        record = self._runner_record()
        response = self._staff_client().get(self._change_url(record.pk))
        body = response.content.decode().lower()
        for token in ("//cdn.", "unpkg.com", "jsdelivr.net", "cloudflare.com"):
            self.assertNotIn(token, body)

    def test_post_returns_405(self):
        record = self._runner_record()
        response = self._staff_client().post(self._change_url(record.pk), data={})
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response["Allow"])

    def test_unknown_pk_returns_redirect_or_404(self):
        response = self._staff_client().get(self._change_url(999_999))
        # Django's admin returns 302 to changelist for nonexistent objects via
        # `_get_obj_does_not_exist_redirect`; matching that behavior is fine.
        self.assertIn(response.status_code, (302, 404))


class TestGraphViewAuth(_BaseLLMRunnerAdminTest):
    def test_anonymous_redirected_to_login_no_graph_in_body(self):
        record = self._runner_record()
        response = Client().get(self._change_url(record.pk))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertNotIn(b"runner-topology-root", response.content)
        self.assertNotIn(b"RunnerTopologyWidget.mount", response.content)

    def test_non_staff_rejected_no_graph_in_body(self):
        record = self._runner_record()
        response = self._non_staff_client().get(self._change_url(record.pk))
        # admin_view redirects non-staff to admin login — same shape as the
        # topology endpoint and the unchanged legacy URL.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
        self.assertNotIn(b"runner-topology-root", response.content)
        self.assertNotIn(b"RunnerTopologyWidget.mount", response.content)


class TestGraphViewObjectPermission(_BaseLLMRunnerAdminTest):
    """Per-object permission denial path: logged-in staff who passes the
    `admin_view` staff gate but fails `has_view_permission(obj)` should get
    a 403 from the graph view, not a redirect or a leaked page.
    """

    def test_staff_without_object_view_permission_gets_403(self):
        record = self._runner_record()
        with patch.object(LLMRunnerAdmin, "has_view_permission", return_value=False):
            response = self._staff_client().get(self._change_url(record.pk))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"runner-topology-root", response.content)


class TestLegacyView(_BaseLLMRunnerAdminTest):
    def test_staff_get_renders_inline_form_not_graph(self):
        record = self._runner_record()
        response = self._staff_client().get(self._legacy_url(record.pk))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # The legacy URL must not render the graph mount target.
        self.assertNotIn(GRAPH_MOUNT_TARGET, body)
        self.assertNotIn(GRAPH_MOUNT_CALL, body)
        # Stable markers from Django's admin change form: a <form> posting back
        # to the same URL, and the readonly `name` field rendered by the parent
        # admin's change view.
        self.assertIn("<form", body)
        self.assertIn(record.name, body)

    def test_staff_post_to_legacy_is_handled_not_405(self):
        record = self._runner_record()
        # An empty POST will fail validation and re-render with errors (200) or
        # be processed by Django admin's standard machinery. The point is that
        # POST on the legacy URL is NOT 405-rejected — proving the URL still
        # delegates to the parent's change_view for save semantics.
        response = self._staff_client().post(self._legacy_url(record.pk), data={})
        self.assertNotEqual(response.status_code, 405)

    def test_anonymous_redirected(self):
        record = self._runner_record()
        response = Client().get(self._legacy_url(record.pk))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])

    def test_non_staff_rejected(self):
        record = self._runner_record()
        response = self._non_staff_client().get(self._legacy_url(record.pk))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])


class TestChangelist(_BaseLLMRunnerAdminTest):
    def test_changelist_renders_with_name_column(self):
        self._runner_record()
        url = reverse("admin:baseapp_ai_langkit_runners_llmrunner_changelist")
        response = self._staff_client().get(url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("column-name", body)


class TestInlineScriptAudit(_BaseLLMRunnerAdminTest):
    """The graph page's only template-authored inline script SHALL be the
    single `RunnerTopologyWidget.mount(...)` call. No function definitions,
    fetches, or event listeners should be added by this template.
    """

    _INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)

    def test_inline_script_is_exactly_the_mount_call(self):
        record = self._runner_record()
        response = self._staff_client().get(self._change_url(record.pk))
        body = response.content.decode()

        inline_blocks = self._INLINE_SCRIPT_RE.findall(body)
        mount_blocks = [b for b in inline_blocks if "RunnerTopologyWidget.mount" in b]
        self.assertEqual(len(mount_blocks), 1)

        mount_block = mount_blocks[0]
        for forbidden in ("function ", "fetch(", "addEventListener", "XMLHttpRequest"):
            self.assertNotIn(forbidden, mount_block)
