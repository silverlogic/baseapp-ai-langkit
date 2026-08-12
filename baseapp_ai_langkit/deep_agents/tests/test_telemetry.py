"""Unit tests for run telemetry: which skills were read, and prompt-cache accounting."""

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, HumanMessage

from baseapp_ai_langkit.deep_agents.telemetry.cache import cache_usage
from baseapp_ai_langkit.deep_agents.telemetry.skills import (
    loaded_skill_dirs,
    skills_read,
)


def _read_call(path: str, key: str = "file_path") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "read_file", "args": {key: path}, "id": "c1", "type": "tool_call"}],
    )


class SkillsReadTests(SimpleTestCase):
    def test_finds_skills_in_first_use_order_deduped(self):
        messages = [
            HumanMessage("q"),
            _read_call("/skills/deals/SKILL.md"),
            _read_call("/skills/case-header/SKILL.md", key="path"),
            _read_call("/skills/deals/SKILL.md"),
        ]
        self.assertEqual(skills_read(messages), ["deals", "case-header"])
        self.assertEqual(loaded_skill_dirs(messages), {"deals", "case-header"})

    def test_a_run_that_read_no_skill_reports_none(self):
        self.assertEqual(skills_read([_read_call("/notes/scratch.md")]), [])

    def test_tolerates_dict_shaped_messages_and_calls(self):
        messages = [{"tool_calls": [{"args": {"file_path": "/skills/deals/SKILL.md"}}]}]
        self.assertEqual(skills_read(messages), ["deals"])

    def test_ignores_calls_whose_args_are_not_a_mapping(self):
        self.assertEqual(skills_read([{"tool_calls": [{"args": "nope"}]}]), [])


class CacheUsageTests(SimpleTestCase):
    def _call(self, **details) -> AIMessage:
        return AIMessage(
            content="",
            usage_metadata={
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
                "input_token_details": details,
            },
        )

    def test_aggregates_reads_and_creation(self):
        usage = cache_usage([self._call(cache_read=800, cache_creation=100)])
        self.assertEqual(usage["cache_read_tokens"], 800)
        self.assertEqual(usage["cache_creation_tokens"], 100)
        self.assertEqual(usage["uncached_input_tokens"], 100)
        self.assertEqual(usage["cache_hit_rate"], 0.8)

    def test_falls_back_to_the_per_ttl_creation_keys(self):
        usage = cache_usage(
            [self._call(ephemeral_5m_input_tokens=60, ephemeral_1h_input_tokens=40)]
        )
        self.assertEqual(usage["cache_creation_tokens"], 100)

    def test_a_provider_that_reports_no_cache_details_reads_zero(self):
        """OpenAI caches server-side without these fields; a 0 is accounting, not a regression."""
        usage = cache_usage([self._call()])
        self.assertEqual(usage["cache_read_tokens"], 0)
        self.assertEqual(usage["cache_hit_rate"], 0.0)
        self.assertEqual(usage["input_tokens"], 1000)

    def test_a_run_with_no_model_calls_is_all_zeroes(self):
        usage = cache_usage([HumanMessage("q"), AIMessage(content="replayed")])
        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["cache_hit_rate"], 0.0)
