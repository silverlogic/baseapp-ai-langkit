from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import TestCase

from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.runners.tests.factories import (
    LLMRunnerFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeUsagePromptFactory,
)
from baseapp_ai_langkit.runners.topology.extractor import _walk_graph, extract_topology
from baseapp_ai_langkit.runners.topology.tests.conftest import audited_extraction


def _make_graph(nodes, edges):
    return SimpleNamespace(
        nodes={key: SimpleNamespace(id=key) for key in nodes},
        edges=[SimpleNamespace(source=s, target=t, conditional=c) for (s, t, c) in edges],
    )


class _PromptedWorker(LLMNodeInterface):
    usage_prompt_schema = BasePromptSchema(
        description="Worker that does X.",
        prompt="Use {placeholder} for X.",
        required_placeholders=["placeholder"],
    )

    def invoke(self, *args, **kwargs):
        pass


class _BarePromptlessWorker(LLMNodeInterface):
    def invoke(self, *args, **kwargs):
        pass


class TestExtractTopologyHappyPath(TestCase):
    def test_default_chat_runner_returns_nodes_and_no_error(self):
        from baseapp_ai_langkit.runners.models import LLMRunner

        runner_record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )

        with audited_extraction() as captured_audits:
            payload = extract_topology(runner_record)

        self.assertIsNone(payload["error"])
        node_keys = [n["key"] for n in payload["nodes"]]
        self.assertEqual(node_keys, ["general_llm"])
        self.assertEqual(payload["nodes"][0]["kind"], "worker")
        self.assertEqual(captured_audits[0].llm_calls, 0)
        self.assertEqual(captured_audits[0].db_writes, 0)


class TestWalkGraphFilter(TestCase):
    """The walker drops anything not declared in runner.get_available_nodes()."""

    def _runner_with_keys(self, *keys):
        attrs = {
            "nodes": {key: _BarePromptlessWorker for key in keys},
            "run": lambda self: None,
            "get_workflow_class": classmethod(lambda cls: BaseWorkflow),
        }
        return type("_TestRunner", (BaseRunnerInterface,), attrs)

    def test_filters_out_nodes_not_declared_on_runner(self):
        runner_class = self._runner_with_keys("a", "b")
        graph = _make_graph(
            nodes=["__start__", "a", "b", "maybe_rollback_memory", "__end__"],
            edges=[
                ("__start__", "a", False),
                ("a", "b", False),
                ("b", "maybe_rollback_memory", False),
                ("maybe_rollback_memory", "__end__", True),
            ],
        )

        nodes, edges = _walk_graph(graph, runner_class, MagicMock())

        self.assertEqual([n["key"] for n in nodes], ["a", "b"])
        self.assertEqual(
            edges,
            [{"source": "a", "target": "b", "kind": "normal"}],
        )

    def test_tags_conditional_edges(self):
        runner_class = self._runner_with_keys("orchestrator", "agent_a", "synthesis")
        graph = _make_graph(
            nodes=["orchestrator", "agent_a", "synthesis"],
            edges=[
                ("orchestrator", "agent_a", True),
                ("agent_a", "synthesis", False),
            ],
        )

        _, edges = _walk_graph(graph, runner_class, MagicMock())

        self.assertEqual(
            edges,
            [
                {"source": "orchestrator", "target": "agent_a", "kind": "conditional"},
                {"source": "agent_a", "target": "synthesis", "kind": "normal"},
            ],
        )


class TestUsagePromptPayload(TestCase):
    def _runner_class_with_node(self, key, node_class):
        attrs = {
            "nodes": {key: node_class},
            "run": lambda self: None,
            "get_workflow_class": classmethod(lambda cls: BaseWorkflow),
        }
        return type("_TestRunner", (BaseRunnerInterface,), attrs)

    def test_node_with_schema_returns_default_and_null_override(self):
        runner_class = self._runner_class_with_node("a", _PromptedWorker)
        runner_record = LLMRunnerFactory(name=f"{runner_class.__module__}.{runner_class.__name__}")
        graph = _make_graph(
            nodes=["a"],
            edges=[],
        )

        nodes, _ = _walk_graph(graph, runner_class, runner_record)

        usage = nodes[0]["usage_prompt"]
        self.assertEqual(usage["description"], "Worker that does X.")
        self.assertEqual(usage["required_placeholders"], ["placeholder"])
        self.assertEqual(usage["default_text"], "Use {placeholder} for X.")
        self.assertIsNone(usage["override"])

    def test_node_without_schema_omits_usage_prompt(self):
        runner_class = self._runner_class_with_node("b", _BarePromptlessWorker)
        runner_record = LLMRunnerFactory(name=f"{runner_class.__module__}.{runner_class.__name__}")
        graph = _make_graph(
            nodes=["b"],
            edges=[],
        )

        nodes, _ = _walk_graph(graph, runner_class, runner_record)

        self.assertIsNone(nodes[0]["usage_prompt"])

    def test_admin_override_reflected_after_save(self):
        runner_class = self._runner_class_with_node("a", _PromptedWorker)
        runner_record = LLMRunnerFactory(name=f"{runner_class.__module__}.{runner_class.__name__}")
        node_record = LLMRunnerNodeFactory(runner=runner_record, node="a")
        LLMRunnerNodeUsagePromptFactory(
            runner_node=node_record,
            usage_prompt="Custom override using {placeholder}",
        )
        graph = _make_graph(nodes=["a"], edges=[])

        nodes, _ = _walk_graph(graph, runner_class, runner_record)

        override = nodes[0]["usage_prompt"]["override"]
        self.assertEqual(override["text"], "Custom override using {placeholder}")
        self.assertIsNotNone(override["saved_at"])
        # default is unchanged
        self.assertEqual(nodes[0]["usage_prompt"]["default_text"], "Use {placeholder} for X.")


class TestExtractTopologyErrorCodes(TestCase):
    def test_runner_unregistered_returns_structured_error(self):
        runner_record = LLMRunnerFactory(name="unknown.module.UnregisteredRunner")

        payload = extract_topology(runner_record)

        self.assertEqual(payload["error"]["code"], "runner_unregistered")
        self.assertEqual(payload["nodes"], [])
        self.assertEqual(payload["edges"], [])

    def test_topology_builder_not_declared_returns_structured_error(self):
        # A runner whose get_workflow_class raises NotImplementedError.
        class _NoWorkflowRunner(BaseRunnerInterface):
            def run(self):
                pass

            @classmethod
            def get_workflow_class(cls):
                raise NotImplementedError("no workflow class for test")

        runner_record = MagicMock()
        runner_record.runner_class = _NoWorkflowRunner

        payload = extract_topology(runner_record)

        self.assertEqual(payload["error"]["code"], "topology_builder_not_declared")
        self.assertEqual(payload["nodes"], [])
        self.assertEqual(payload["edges"], [])

    def test_workflow_init_failed_when_node_init_raises(self):
        class _BoomNode(LLMNodeInterface):
            def __init__(self, *args, **kwargs):
                raise RuntimeError("kaboom")

            def invoke(self, *args, **kwargs):
                pass

        class _BoomRunner(BaseRunnerInterface):
            nodes = {"boom": _BoomNode}

            def run(self):
                pass

            @classmethod
            def get_workflow_class(cls):
                return BaseWorkflow

        runner_record = MagicMock()
        runner_record.runner_class = _BoomRunner

        payload = extract_topology(runner_record)

        self.assertEqual(payload["error"]["code"], "workflow_init_failed")

    def test_unknown_error_for_unexpected_exception_outside_build(self):
        # Force the registry lookup to succeed but graph walk to blow up
        runner_class = type(
            "_GraphBoom",
            (BaseRunnerInterface,),
            {
                "nodes": {},
                "run": lambda self: None,
                "get_workflow_class": classmethod(lambda cls: BaseWorkflow),
                "build_topology_workflow": classmethod(
                    lambda cls, **kw: SimpleNamespace(
                        workflow_chain=SimpleNamespace(
                            get_graph=lambda: (_ for _ in ()).throw(RuntimeError("graph-boom"))
                        )
                    )
                ),
            },
        )
        runner_record = MagicMock()
        runner_record.runner_class = runner_class

        payload = extract_topology(runner_record)

        self.assertEqual(payload["error"]["code"], "unknown")


class TestNoSideEffectsDuringExtraction(TestCase):
    def test_no_llm_or_db_writes_during_default_chat_runner_extraction(self):
        from baseapp_ai_langkit.runners.models import LLMRunner

        runner_record, _ = LLMRunner.objects.get_or_create(
            name=f"{DefaultChatRunner.__module__}.{DefaultChatRunner.__name__}"
        )

        with audited_extraction() as captured:
            extract_topology(runner_record)

        self.assertEqual(captured[0].llm_calls, 0)
        self.assertEqual(captured[0].db_writes, 0)
