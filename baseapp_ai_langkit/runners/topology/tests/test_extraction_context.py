from django.contrib.auth import get_user_model
from django.test import TestCase
from langgraph.checkpoint.memory import MemorySaver

from baseapp_ai_langkit.runners.topology.extraction_context import (
    TopologyExtractionAudit,
    topology_extraction_context,
)


class TestTopologyExtractionContext(TestCase):
    def test_yields_stub_llm_that_raises_and_increments_audit(self):
        with topology_extraction_context() as ctx:
            self.assertEqual(ctx.audit.llm_calls, 0)
            with self.assertRaises(RuntimeError):
                ctx.llm.invoke([])
            self.assertEqual(ctx.audit.llm_calls, 1)

    def test_yields_in_memory_checkpointer(self):
        with topology_extraction_context() as ctx:
            self.assertIsInstance(ctx.checkpointer, MemorySaver)

    def test_yields_stub_runnable_config(self):
        with topology_extraction_context() as ctx:
            self.assertEqual(ctx.config, {"configurable": {"thread_id": "topology-extraction"}})

    def test_audit_tracks_db_writes(self):
        with topology_extraction_context() as ctx:
            self.assertEqual(ctx.audit.db_writes, 0)
            User = get_user_model()
            User.objects.create(username="topology-test-user")
            self.assertGreaterEqual(ctx.audit.db_writes, 1)

    def test_audit_starts_at_zero_for_each_invocation(self):
        with topology_extraction_context() as ctx:
            with self.assertRaises(RuntimeError):
                ctx.llm.invoke([])
        with topology_extraction_context() as ctx2:
            self.assertEqual(ctx2.audit.llm_calls, 0)
            self.assertEqual(ctx2.audit.db_writes, 0)


class TestTopologyExtractionAudit(TestCase):
    def test_default_counters_are_zero(self):
        audit = TopologyExtractionAudit()
        self.assertEqual(audit.llm_calls, 0)
        self.assertEqual(audit.db_writes, 0)
