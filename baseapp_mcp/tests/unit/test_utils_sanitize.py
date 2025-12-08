from baseapp_mcp.utils import sanitize_sensitive_dict


class TestSanitizeUtils:
    def test_sanitize_replaces_sensitive_values_in_top_level_and_nested_and_lists(self):
        data = {
            "email": "user@example.com",
            "access_token": "super-secret",
            "profile": {
                "name": "Tester",
                "credentials": {"password": "hunter2", "Secret": "s2"},
                "details": {"preferences": {"api_key": "key-xyz"}},
            },
            "sessions": [
                {"meta": {"token": "tok-1"}},
                "note: do not redact",
            ],
        }

        sensitive_keys = {"access_token", "password", "token", "secret", "api_key"}

        sanitized = sanitize_sensitive_dict(data, sensitive_keys)

        # top-level replacement
        assert sanitized["access_token"] == "__REDACTED__"

        # nested dict replacement (one level deeper)
        assert sanitized["profile"]["credentials"]["password"] == "__REDACTED__"

        # nested dict with different case for key
        assert sanitized["profile"]["credentials"]["Secret"] == "__REDACTED__"

        # deeper nested replacement (preferences -> api_key)
        assert sanitized["profile"]["details"]["preferences"]["api_key"] == "__REDACTED__"

        # list item: dict inside list should be sanitized at nested path
        assert isinstance(sanitized["sessions"], list)
        assert sanitized["sessions"][0]["meta"]["token"] == "__REDACTED__"

        # non-dict list items remain unchanged
        assert sanitized["sessions"][1] == "note: do not redact"

    def test_custom_mask_and_case_insensitive_keys(self):
        data = {"Api_Key": "abc123", "nested": {"Secret": "s"}}
        sensitive_keys = {"api_key", "secret"}

        sanitized = sanitize_sensitive_dict(data, sensitive_keys, mask="[REDACTED]")

        assert sanitized["Api_Key"] == "[REDACTED]"
        assert sanitized["nested"]["Secret"] == "[REDACTED]"

    def test_empty_data_returns_empty_dict(self):
        assert sanitize_sensitive_dict({}, set()) == {}
