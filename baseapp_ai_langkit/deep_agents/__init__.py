"""Generic deep-agent runtime, built on ``deepagents``.

Product-agnostic machinery for running one autonomous agent: the construction point
(:mod:`.builder`), the configurable node (:mod:`.node`), the soft and hard resource
limits (:mod:`.limits`), control over which built-in tools a surface gets
(:mod:`.tool_scoping`), skill loading and composition (:mod:`.skills`), run telemetry
(:mod:`.telemetry`), and a scripted model for deterministic tests (:mod:`.testing`).

Requires the ``deep-agents`` extra. Nothing here is imported by the rest of langkit,
so a project that does not install the extra is unaffected.
"""

__all__ = [
    "builder",
    "limits",
    "node",
    "skills",
    "telemetry",
    "testing",
    "tool_scoping",
]
