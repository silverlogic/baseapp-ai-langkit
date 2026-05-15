"""Tests for the F03-S01 runtime override wiring in `BaseRunnerInterface`.

`_build_runner_default_llm()` is rung 2 of the resolution chain — consulted
when `_build_override_llm(node_key)` returned None. Mirrors the per-node
helper one rung higher; adds a per-execution memoization that caps DB
queries + initializer.initialize() at exactly one call per runner instance.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
    LLMRunnerDefaultModelOverrideFactory,
    LLMRunnerFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeModelOverrideFactory,
)

NODE_KEY = "general_llm"


def _runner_record():
    record, _ = LLMRunnerFactory._meta.model.objects.get_or_create(
        name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
    )
    return record


def _make_runner_instance() -> DefaultChatRunner:
    """Build a `DefaultChatRunner` instance without running __init__ (it expects
    a real ChatSession). We only test methods on `BaseRunnerInterface`."""
    return DefaultChatRunner.__new__(DefaultChatRunner)


class TestBuildRunnerDefaultLLMNoRecord(TestCase):
    def test_no_runner_record(self):
        """No `LLMRunner` row → `_build_runner_default_llm` returns None."""
        runner = _make_runner_instance()
        _runner_record().delete()
        self.assertIsNone(runner._build_runner_default_llm())

    def test_no_runner_default_override_row(self):
        """Runner record exists but no `LLMRunnerDefaultModelOverride` row → None."""
        runner = _make_runner_instance()
        _runner_record()
        self.assertIsNone(runner._build_runner_default_llm())


class TestBuildRunnerDefaultLLMHappyPath(TestCase):
    def test_in_catalog_override_builds_via_initializer_with_merged_params(self):
        record = _runner_record()
        AvailableLLMModelFactory(
            initializer_key="openai",
            model_id="gpt-4-runner-merge",
            default_params={"max_tokens": 256},
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="openai",
            model_id="gpt-4-runner-merge",
            params={"temperature": 0.7},
        )

        runner = _make_runner_instance()
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai.OpenAIInitializer.initialize",
            return_value=MagicMock(name="runner-default-chat-model"),
        ) as mock_init:
            built = runner._build_runner_default_llm()

        # Catalog defaults merged UNDER override params (override wins per key).
        mock_init.assert_called_once_with("gpt-4-runner-merge", max_tokens=256, temperature=0.7)
        self.assertIs(built, mock_init.return_value)


class TestBuildRunnerDefaultLLMOrphanFallback(TestCase):
    def test_unregistered_initializer_falls_back_and_warns(self):
        record = _runner_record()
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="not-a-registered-key",
            model_id="anything",
        )

        runner = _make_runner_instance()
        with self.assertLogs(
            "baseapp_ai_langkit.base.interfaces.base_runner", level="WARNING"
        ) as captured:
            built = runner._build_runner_default_llm()

        self.assertIsNone(built)
        joined = "\n".join(captured.output)
        self.assertIn("runner-level default model override", joined)
        self.assertIn("not-a-registered-key", joined)

    def test_missing_catalog_row_falls_back_and_warns(self):
        record = _runner_record()
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-not-in-catalog",
        )

        runner = _make_runner_instance()
        with self.assertLogs(
            "baseapp_ai_langkit.base.interfaces.base_runner", level="WARNING"
        ) as captured:
            built = runner._build_runner_default_llm()

        self.assertIsNone(built)
        joined = "\n".join(captured.output)
        self.assertIn("runner-level default model override", joined)
        self.assertIn("missing catalog entry", joined)
        self.assertIn("claude-not-in-catalog", joined)


class TestBuildRunnerDefaultLLMMemoization(TestCase):
    """Rule: the helper memoizes its result on `self` for the lifetime of one
    execution. Subsequent calls SHALL NOT re-query the DB, re-resolve the
    initializer, or re-invoke `initialize(...)`."""

    def test_two_consecutive_calls_hit_initializer_once(self):
        record = _runner_record()
        AvailableLLMModelFactory(
            initializer_key="openai",
            model_id="gpt-4-memo-test",
            default_params={},
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="openai",
            model_id="gpt-4-memo-test",
            params={},
        )

        runner = _make_runner_instance()
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai.OpenAIInitializer.initialize",
            return_value=MagicMock(name="cached-chat-model"),
        ) as mock_init:
            first = runner._build_runner_default_llm()
            second = runner._build_runner_default_llm()
            third = runner._build_runner_default_llm()

        self.assertEqual(mock_init.call_count, 1)
        self.assertIs(first, mock_init.return_value)
        self.assertIs(second, mock_init.return_value)
        self.assertIs(third, mock_init.return_value)

    def test_orphan_warning_fires_only_once_per_execution(self):
        """Orphan path's `logger.warning` fires once per `self`, not per call."""
        record = _runner_record()
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-orphan-test",
        )

        runner = _make_runner_instance()
        with self.assertLogs(
            "baseapp_ai_langkit.base.interfaces.base_runner", level="WARNING"
        ) as captured:
            self.assertIsNone(runner._build_runner_default_llm())
            self.assertIsNone(runner._build_runner_default_llm())
            self.assertIsNone(runner._build_runner_default_llm())

        warning_lines = [line for line in captured.output if "runner-level" in line]
        self.assertEqual(len(warning_lines), 1)

    def test_none_result_is_cached_separately_from_uninitialized(self):
        """Sentinel distinguishes 'not computed' from 'computed and None'."""
        _runner_record()  # no override row → first call returns None
        runner = _make_runner_instance()

        # First call: returns None and caches None.
        first = runner._build_runner_default_llm()
        self.assertIsNone(first)

        # Subsequent calls return the cached None WITHOUT re-doing the DB lookup.
        # We assert this by spying on the resolver — second call MUST NOT
        # invoke the underlying resolve method.
        with patch.object(DefaultChatRunner, "_resolve_runner_default_llm") as mock_resolve:
            second = runner._build_runner_default_llm()
        mock_resolve.assert_not_called()
        self.assertIsNone(second)

    def test_two_independent_runner_instances_do_not_share_cache(self):
        record = _runner_record()
        AvailableLLMModelFactory(
            initializer_key="openai",
            model_id="gpt-4-isolation-test",
            default_params={},
        )
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="openai",
            model_id="gpt-4-isolation-test",
            params={},
        )

        runner_a = _make_runner_instance()
        runner_b = _make_runner_instance()
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai.OpenAIInitializer.initialize",
            return_value=MagicMock(name="chat-model"),
        ) as mock_init:
            runner_a._build_runner_default_llm()
            runner_b._build_runner_default_llm()

        # Each instance resolves independently — two DB+initialize round-trips.
        self.assertEqual(mock_init.call_count, 2)


class TestResolutionChainWiring(TestCase):
    """`get_dynamic_node_config` wires per-node → runner-level via short-circuit `or`."""

    def test_per_node_override_short_circuits_runner_level(self):
        """When per-node returns non-None, runner-level helper must NOT be called."""
        record = _runner_record()
        node = LLMRunnerNodeFactory(runner=record, node=NODE_KEY)
        AvailableLLMModelFactory(initializer_key="openai", model_id="gpt-4o-mini")
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="openai",
            model_id="gpt-4o-mini",
            params={"temperature": 0.2},
        )
        # Runner-level row also exists, but per-node should win.
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
        )

        runner = _make_runner_instance()
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai.OpenAIInitializer.initialize",
            return_value=MagicMock(name="per-node-llm"),
        ):
            with patch.object(
                DefaultChatRunner,
                "_build_runner_default_llm",
                side_effect=AssertionError("runner-level must not be called"),
            ) as mock_runner_default:
                cfg = runner.get_dynamic_node_config(NODE_KEY, DefaultChatRunner.nodes[NODE_KEY])

        mock_runner_default.assert_not_called()
        self.assertIsNotNone(cfg.llm)

    def test_runner_level_fills_in_when_per_node_returns_none(self):
        """No per-node row → fallthrough to runner-level rung."""
        record = _runner_record()
        # No per-node row. Runner-level row exists.
        AvailableLLMModelFactory(initializer_key="anthropic", model_id="claude-sonnet-4-6")
        LLMRunnerDefaultModelOverrideFactory(
            runner=record,
            initializer_key="anthropic",
            model_id="claude-sonnet-4-6",
            params={"temperature": 0.4},
        )

        runner = _make_runner_instance()
        fake_chat = MagicMock(name="runner-level-llm")
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.anthropic.AnthropicInitializer.initialize",
            return_value=fake_chat,
        ):
            cfg = runner.get_dynamic_node_config(NODE_KEY, DefaultChatRunner.nodes[NODE_KEY])

        self.assertIs(cfg.llm, fake_chat)

    def test_neither_rung_yields_none_llm(self):
        """No per-node row, no runner-level row → NodeConfig.llm is None
        (caller substitutes the code-declared default)."""
        _runner_record()  # no overrides anywhere
        runner = _make_runner_instance()
        cfg = runner.get_dynamic_node_config(NODE_KEY, DefaultChatRunner.nodes[NODE_KEY])
        self.assertIsNone(cfg.llm)
