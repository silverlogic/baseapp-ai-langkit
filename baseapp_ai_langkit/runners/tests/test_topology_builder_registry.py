from django.test import TestCase
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langgraph.checkpoint.memory import MemorySaver

from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow
from baseapp_ai_langkit.runners.registry import RunnerRegistry


class TestRegisteredRunnersDeclareTopologyBuilder(TestCase):
    """Every @register_runner'd class must implement build_topology_workflow().

    Runs against the live registry — no mocking — so we catch missing
    implementations as soon as a runner is added.
    """

    def test_every_registered_runner_builds_a_topology_workflow(self):
        registered = RunnerRegistry.get_all()
        self.assertGreater(
            len(registered),
            0,
            "Registry is empty — at least one runner must be registered for this contract test.",
        )

        stub_llm = FakeChatModel()
        stub_config = {"configurable": {"thread_id": "topology-extraction"}}
        for runner_cls in registered:
            with self.subTest(runner=runner_cls.__name__):
                workflow = runner_cls.build_topology_workflow(
                    llm=stub_llm,
                    config=stub_config,
                    checkpointer=MemorySaver(),
                )
                self.assertIsInstance(
                    workflow,
                    BaseWorkflow,
                    f"{runner_cls.__name__}.build_topology_workflow must return a BaseWorkflow",
                )
