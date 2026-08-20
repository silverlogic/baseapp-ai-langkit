"""Detect which skills an agent loaded during a run, from its message trace.

A skill is "used" only when the agent reads its ``SKILL.md`` through a filesystem
tool: with progressive disclosure, loading a skill *is* reading its file. Production
runs and skill-trigger evals key off the same signal, so the extraction lives here
once.

Kept dependency-light (stdlib only) so it imports from the production agent path and
from pure, no-DB/no-LLM tests alike. The tool-call shape and the path argument key
(``file_path`` vs ``path``) are not pinned across deepagents and langchain versions,
so the scan is deliberately tolerant: it walks object- and dict-shaped messages and
matches a SKILL.md path in any string argument.
"""

import re
from typing import Any, Iterable, Iterator, List, Set

#: Virtual-filesystem prefix the skills middleware mounts skills under. Duplicated from
#: `deep_agents.skills.files` on purpose: this module stays stdlib-only so the eval and
#: scoring paths can import it without pulling the agent build chain in.
SKILLS_ROOT = "/skills/"

#: Matches "/skills/<dir>/SKILL.md" anywhere in a tool-call argument value.
_SKILL_PATH = re.compile(rf"{re.escape(SKILLS_ROOT)}([^/\s]+)/SKILL\.md")


def iter_tool_calls(messages: Iterable[Any]) -> Iterator[Any]:
    """Yield every tool call across the trace, tolerant of message shapes."""
    for message in messages:
        calls = getattr(message, "tool_calls", None)
        if not calls and isinstance(message, dict):
            calls = message.get("tool_calls")
        for call in calls or []:
            yield call


def skills_read(messages: Iterable[Any]) -> List[str]:
    """Skill **directory** names whose SKILL.md was read, in first-use order, deduped."""
    found: List[str] = []
    seen: Set[str] = set()
    for call in iter_tool_calls(messages):
        if isinstance(call, dict):
            args = call.get("args", call)  # fall back to the whole call dict
        else:
            args = getattr(call, "args", None)
        if not isinstance(args, dict):
            continue
        for value in args.values():
            if isinstance(value, str):
                for name in _SKILL_PATH.findall(value):
                    if name not in seen:
                        seen.add(name)
                        found.append(name)
    return found


def loaded_skill_dirs(messages: Iterable[Any]) -> Set[str]:
    """Set form of :func:`skills_read`, for order-insensitive callers."""
    return set(skills_read(messages))
