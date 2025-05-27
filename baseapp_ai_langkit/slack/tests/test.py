import json
import re

import httpretty
from django.test import TestCase


class SlackTestCase(TestCase):
    def setUp(self):
        super().setUp()
        httpretty.enable(allow_net_connect=False)

    def tearDown(self):
        super().tearDown()
        httpretty.disable()
        httpretty.reset()

    def mock_slack_api_call(self, endpoint, method=httpretty.POST, response_data=None, status=200):
        if response_data is None:
            response_data = {"ok": True}

        httpretty.register_uri(
            method,
            re.compile(f"https://(www.)?slack.com/api/{endpoint}"),
            body=json.dumps(response_data),
            content_type="application/json",
            status=status,
        )

    def assert_slack_api_call(
        self, endpoint, expected_body=None, method=httpretty.POST, call_index=0
    ):
        url_pattern = re.compile(f"https://(www.)?slack.com/api/{endpoint}")
        matching_requests = [
            req for req in httpretty.latest_requests() if url_pattern.match(req.url)
        ]

        self.assertTrue(
            len(matching_requests) > call_index,
            f"No request made to {endpoint} at index {call_index}",
        )

        request = matching_requests[call_index]
        self.assertEqual(request.method, method)

        if expected_body:
            actual_body = json.loads(request.body.decode("utf-8"))
            self.assertEqual(actual_body, expected_body)

        return request

    def dummy_event_id(self) -> str:
        return "Ev0XXXXXXXXX"

    def dummy_real_user_id(self) -> str:
        return "UXXXXXXXXXX"

    def dummy_bot_user_id(self) -> str:
        return "UYYYYYYYY"

    def dummy_channel_id(self) -> str:
        """
        Dummy channel id for a non-private channel
        """
        return "CXXXXXXXXXA"

    def dummy_im_channel_id(self) -> str:
        """
        Dummy channel id for an im channel
        """
        return "DXXXXXXXXXM"

    def user_profile_data(self):
        return {
            "ok": True,
            "profile": {
                "title": "Software Engineer | SPARKLE",
                "phone": "5555555555",
                "skype": "",
                "real_name": "First Last",
                "real_name_normalized": "First Last",
                "display_name": "fl",
                "display_name_normalized": "fl",
                "fields": {"XXXXXXXXXXXX": {"value": "Software Engineer | SPARKLE", "alt": ""}},
                "status_text": "",
                "status_emoji": "",
                "status_emoji_display_info": [],
                "status_expiration": 0,
                "avatar_hash": "XXXXXXXXXXXX",
                "image_original": "https://picsum.photos/1024",
                "is_custom_image": True,
                "email": "fl@tsl.io",
                "huddle_state": "default_unset",
                "huddle_state_expiration_ts": 0,
                "first_name": "First",
                "last_name": "Last",
                "image_24": "https://picsum.photos/24",
                "image_32": "https://picsum.photos/32",
                "image_48": "https://picsum.photos/48",
                "image_72": "https://picsum.photos/72",
                "image_192": "https://picsum.photos/192",
                "image_512": "https://picsum.photos/512",
                "image_1024": "https://picsum.photos/1024",
                "status_text_canonical": "",
            },
        }

    def bot_user_profile_data(self):
        return {
            "ok": True,
            "profile": {
                "api_app_id": "TEST643TEST",
            },
        }

    def conversations_info_data(self):
        return {
            "ok": True,
            "channel": {
                "name": "pytest",
            },
        }
