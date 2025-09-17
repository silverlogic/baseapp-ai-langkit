import hashlib
import hmac
import time
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory

from baseapp_ai_langkit.slack.permissions import isSlackRequestSigned

from .test import SlackTestCase


class TestSlackPermissions(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.permission = isSlackRequestSigned()
        self.factory = APIRequestFactory()
        self.view = MagicMock()
        self.slack_signing_secret = "test_signing_secret"

        # Patch settings to use test signing secret
        self.settings_patch = patch("baseapp_ai_langkit.slack.permissions.settings")
        self.mock_settings = self.settings_patch.start()
        self.mock_settings.SLACK_SIGNING_SECRET = self.slack_signing_secret

    def tearDown(self):
        super().tearDown()
        self.settings_patch.stop()

    def test_missing_timestamp_header(self):
        request = self.factory.post("/slack/events")
        result = self.permission.has_permission(request, self.view)
        self.assertFalse(result)

    def test_expired_timestamp(self):
        # Create timestamp that's more than 5 minutes old
        old_timestamp = str(int(time.time()) - 301)
        request = self.factory.post("/slack/events", HTTP_X_SLACK_REQUEST_TIMESTAMP=old_timestamp)
        result = self.permission.has_permission(request, self.view)
        self.assertFalse(result)

    def test_missing_signature_header(self):
        current_timestamp = str(int(time.time()))
        request = self.factory.post(
            "/slack/events", HTTP_X_SLACK_REQUEST_TIMESTAMP=current_timestamp
        )
        result = self.permission.has_permission(request, self.view)
        self.assertFalse(result)

    def test_invalid_signature(self):
        current_timestamp = str(int(time.time()))
        request = self.factory.post(
            "/slack/events",
            data='{"test":"data"}',
            content_type="application/json",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=current_timestamp,
            HTTP_X_SLACK_SIGNATURE="v0=invalid_signature",
        )
        result = self.permission.has_permission(request, self.view)
        self.assertFalse(result)

    def test_valid_signature(self):
        current_timestamp = str(int(time.time()))
        body = '{"test":"data"}'

        # Generate valid signature
        req = str.encode(f"v0:{current_timestamp}:") + str.encode(body)
        request_hash = (
            "v0=" + hmac.new(str.encode(self.slack_signing_secret), req, hashlib.sha256).hexdigest()
        )

        request = self.factory.post(
            "/slack/events",
            data=body,
            content_type="application/json",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=current_timestamp,
            HTTP_X_SLACK_SIGNATURE=request_hash,
        )

        result = self.permission.has_permission(request, self.view)
        self.assertTrue(result)

    def test_signature_length_mismatch(self):
        current_timestamp = str(int(time.time()))
        request = self.factory.post(
            "/slack/events",
            data='{"test":"data"}',
            content_type="application/json",
            HTTP_X_SLACK_REQUEST_TIMESTAMP=current_timestamp,
            HTTP_X_SLACK_SIGNATURE="v0=short",
        )

        # Mock hasattr to simulate environments without hmac.compare_digest
        with patch("baseapp_ai_langkit.slack.permissions.hasattr", return_value=False):
            result = self.permission.has_permission(request, self.view)
            self.assertFalse(result)
