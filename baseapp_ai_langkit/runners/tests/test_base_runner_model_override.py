"""Tests for the F02-S02 runtime override wiring in `BaseRunnerInterface`.

`get_dynamic_node_config(node_key, node_class) -> NodeConfig` returns prompts +
an override-built `llm` (when an override row + catalog row + registered
initializer all exist). Orphan paths (no catalog row OR unregistered
initializer) fall back to `llm=None` and emit `logger.warning`.

`get_nodes` and `instantiate_edge_node` consume `cfg.llm` and substitute the
`llm=` kwarg per node.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from baseapp_ai_langkit.base.interfaces.base_runner import (
    BaseRunnerInterface,
    NodeConfig,
)
from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.tests.factories import (
    AvailableLLMModelFactory,
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
    """Make a `DefaultChatRunner` instance without running __init__ (it expects
    a real ChatSession). We only test methods on `BaseRunnerInterface`, not the
    full run() path."""
    return DefaultChatRunner.__new__(DefaultChatRunner)


class TestBuildOverrideLLMNoRecord(TestCase):
    """No override → `_build_override_llm` returns None."""

    def test_no_runner_record(self):
        runner = _make_runner_instance()
        # DefaultChatRunner is auto-synced at post_migrate; delete to simulate
        # the "no record" path.
        _runner_record().delete()
        self.assertIsNone(runner._build_override_llm(NODE_KEY))

    def test_no_node_record(self):
        runner = _make_runner_instance()
        _runner_record()  # record exists; no node row
        self.assertIsNone(runner._build_override_llm(NODE_KEY))

    def test_no_override_row(self):
        runner = _make_runner_instance()
        record = _runner_record()
        LLMRunnerNodeFactory(runner=record, node=NODE_KEY)  # no override
        self.assertIsNone(runner._build_override_llm(NODE_KEY))


class TestBuildOverrideLLMHappyPath(TestCase):
    def test_in_catalog_override_builds_via_initializer(self):
        # Use a model_id distinct from the seeded `gpt-4o-mini` row so we control
        # `default_params` exactly. (`django_get_or_create` on the factory would
        # ignore `defaults={...}` for an already-existing seed row.)
        record = _runner_record()
        node = LLMRunnerNodeFactory(runner=record, node=NODE_KEY)
        AvailableLLMModelFactory(
            initializer_key="openai",
            model_id="gpt-4-test-merge",
            default_params={"max_tokens": 512},
        )
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="openai",
            model_id="gpt-4-test-merge",
            params={"temperature": 0.7},
        )

        runner = _make_runner_instance()
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai" ".OpenAIInitializer.initialize",
            return_value=MagicMock(name="fake-chat-model"),
        ) as mock_init:
            built = runner._build_override_llm(NODE_KEY)

        # Catalog defaults merged UNDER override params (override wins per key).
        mock_init.assert_called_once_with("gpt-4-test-merge", max_tokens=512, temperature=0.7)
        self.assertIs(built, mock_init.return_value)


class TestBuildOverrideLLMOrphanFallback(TestCase):
    def test_unregistered_initializer_falls_back_and_warns(self):
        record = _runner_record()
        node = LLMRunnerNodeFactory(runner=record, node=NODE_KEY)
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="not-a-registered-key",
            model_id="anything",
        )

        runner = _make_runner_instance()
        with self.assertLogs(
            "baseapp_ai_langkit.base.interfaces.base_runner", level="WARNING"
        ) as captured:
            built = runner._build_override_llm(NODE_KEY)
        self.assertIsNone(built)
        joined = "\n".join(captured.output)
        self.assertIn("unregistered initializer_key", joined)
        self.assertIn("not-a-registered-key", joined)

    def test_missing_catalog_row_falls_back_and_warns(self):
        record = _runner_record()
        node = LLMRunnerNodeFactory(runner=record, node=NODE_KEY)
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="anthropic",  # registered initializer
            model_id="claude-not-in-catalog",
        )

        runner = _make_runner_instance()
        with self.assertLogs(
            "baseapp_ai_langkit.base.interfaces.base_runner", level="WARNING"
        ) as captured:
            built = runner._build_override_llm(NODE_KEY)
        self.assertIsNone(built)
        joined = "\n".join(captured.output)
        self.assertIn("missing catalog entry", joined)
        self.assertIn("claude-not-in-catalog", joined)


class TestGetNodesSubstitutesOverrideLlm(TestCase):
    """End-to-end: `get_nodes` substitutes the override-built `llm` per node."""

    def test_override_llm_replaces_default_in_kwargs(self):
        record = _runner_record()
        node = LLMRunnerNodeFactory(runner=record, node=NODE_KEY)
        AvailableLLMModelFactory(initializer_key="openai", model_id="gpt-4o-mini")
        LLMRunnerNodeModelOverrideFactory(
            runner_node=node,
            initializer_key="openai",
            model_id="gpt-4o-mini",
            params={"temperature": 0.4},
        )

        runner = _make_runner_instance()
        default_llm = MagicMock(name="default-llm")
        override_llm = MagicMock(name="override-llm")

        instantiate_calls = []

        def _capture(node_class, *args, **kwargs):
            instantiate_calls.append(kwargs.get("llm"))
            return MagicMock(name="node-instance")

        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai" ".OpenAIInitializer.initialize",
            return_value=override_llm,
        ):
            with patch.object(DefaultChatRunner, "instantiate_node", _capture):
                runner.get_nodes(llm=default_llm, config={})

        # The single declared node received the override-built llm, not the default.
        self.assertEqual(instantiate_calls, [override_llm])

    def test_no_override_keeps_default_llm(self):
        _runner_record()  # node row absent
        runner = _make_runner_instance()
        default_llm = MagicMock(name="default-llm")

        instantiate_calls = []

        def _capture(node_class, *args, **kwargs):
            instantiate_calls.append(kwargs.get("llm"))
            return MagicMock()

        with patch.object(DefaultChatRunner, "instantiate_node", _capture):
            runner.get_nodes(llm=default_llm, config={})

        self.assertEqual(instantiate_calls, [default_llm])


class TestNodeConfigDataclass(TestCase):
    def test_construction_and_attribute_access(self):
        cfg = NodeConfig(llm=None, usage_prompt_schema=None, state_modifier_schema=None)
        self.assertIsNone(cfg.llm)
        self.assertIsNone(cfg.usage_prompt_schema)
        self.assertIsNone(cfg.state_modifier_schema)


class _RunnerWithMetadata(BaseRunnerInterface):
    """Runner used to exercise `BaseRunnerInterface.initialize_llm` directly."""

    default_model_metadata = LLMModelMetadata(
        initializer_key="openai",
        model_id="gpt-4-base-test",
        params={"temperature": 0.5},
    )

    def run(self):  # pragma: no cover — unused in these tests
        return ""

    @classmethod
    def get_workflow_class(cls):  # pragma: no cover
        raise NotImplementedError


class _RunnerWithoutMetadata(BaseRunnerInterface):
    def run(self):  # pragma: no cover
        return ""

    @classmethod
    def get_workflow_class(cls):  # pragma: no cover
        raise NotImplementedError


class _RunnerWithUnregisteredInitializer(BaseRunnerInterface):
    default_model_metadata = LLMModelMetadata(
        initializer_key="not-a-real-initializer",
        model_id="anything",
    )

    def run(self):  # pragma: no cover
        return ""

    @classmethod
    def get_workflow_class(cls):  # pragma: no cover
        raise NotImplementedError


class TestBaseInitializeLLM(SimpleTestCase):
    """`BaseRunnerInterface.initialize_llm` builds from `default_model_metadata`
    via the registered initializer — no per-runner override needed."""

    def test_builds_chat_model_via_registered_initializer(self):
        runner = _RunnerWithMetadata.__new__(_RunnerWithMetadata)
        with patch(
            "baseapp_ai_langkit.runners.model_initializers.openai" ".OpenAIInitializer.initialize",
            return_value=MagicMock(name="fake-chat-model"),
        ) as mock_init:
            llm = runner.initialize_llm()
        mock_init.assert_called_once_with("gpt-4-base-test", temperature=0.5)
        self.assertIs(llm, mock_init.return_value)

    def test_raises_not_implemented_when_metadata_missing(self):
        runner = _RunnerWithoutMetadata.__new__(_RunnerWithoutMetadata)
        with self.assertRaises(NotImplementedError) as ctx:
            runner.initialize_llm()
        self.assertIn("default_model_metadata", str(ctx.exception))

    def test_raises_value_error_when_initializer_unregistered(self):
        runner = _RunnerWithUnregisteredInitializer.__new__(_RunnerWithUnregisteredInitializer)
        with self.assertRaises(ValueError) as ctx:
            runner.initialize_llm()
        self.assertIn("not-a-real-initializer", str(ctx.exception))

    def test_default_chat_runner_uses_base_implementation(self):
        """`DefaultChatRunner` no longer overrides `initialize_llm` — it inherits
        the base implementation that builds from `default_model_metadata`."""
        self.assertIs(
            DefaultChatRunner.initialize_llm,
            BaseRunnerInterface.initialize_llm,
        )
