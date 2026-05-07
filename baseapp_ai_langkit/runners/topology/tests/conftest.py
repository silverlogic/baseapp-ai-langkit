"""Shared fixtures for topology tests.

The audit fixture wraps `extract_topology` and asserts both the LLM-call counter
and the DB-write counter stayed at zero, per rule 9 (no production side effects
during topology extraction).
"""

from contextlib import contextmanager
from unittest.mock import patch

from baseapp_ai_langkit.runners.topology import extraction_context as ec


@contextmanager
def audited_extraction():
    """Yield a list that, after extraction, contains the captured audit object.

    Used by tests to assert `audit.llm_calls == 0` and `audit.db_writes == 0`
    after `extract_topology()` runs.
    """
    captured = []
    original = ec.topology_extraction_context

    @contextmanager
    def wrapped():
        with original() as ctx:
            captured.append(ctx.audit)
            yield ctx

    with patch.object(ec, "topology_extraction_context", wrapped):
        # Also patch the symbol used by the extractor module (it imports by name).
        from baseapp_ai_langkit.runners.topology import extractor

        with patch.object(extractor, "topology_extraction_context", wrapped):
            yield captured
