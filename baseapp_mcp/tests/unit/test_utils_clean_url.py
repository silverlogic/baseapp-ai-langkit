from baseapp_mcp.utils import clean_url


class TestCleanURL:
    def test_adds_https_when_missing(self):
        assert clean_url("example.com/path") == "https://example.com/path"

    def test_strips_trailing_slash(self):
        assert clean_url("https://example.com/path/") == "https://example.com/path"

    def test_removes_query_and_fragment(self):
        assert clean_url("https://example.com/path?x=1&y=2#section") == "https://example.com/path"

    def test_leaves_clean_url_alone(self):
        assert clean_url("https://example.com/path") == "https://example.com/path"

    def test_handles_empty_or_none(self):
        assert clean_url("") == ""
        assert clean_url("   ") == "   "

    def test_upgrades_http_to_https(self):
        assert clean_url("http://example.com/path") == "https://example.com/path"

    def test_normalizes_scheme_relative(self):
        assert clean_url("//example.com/path") == "https://example.com/path"
