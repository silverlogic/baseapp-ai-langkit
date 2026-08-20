"""Turning a skill source into the agent's virtual filesystem payload.

Each skill becomes ``/skills/<dir>/SKILL.md`` in the virtual filesystem deepagents'
skills middleware reads: it parses the frontmatter to advertise the skill and exposes
the body on demand, so the agent only pays for a playbook it decides it needs.

A skill's supporting files ride along at ``/skills/<dir>/<relative path>``. They are not
advertised anywhere and nothing loads them for the agent; the SKILL.md names them and the
agent reads one with ``read_file`` when it decides it applies. That is progressive
disclosure a second time, inside one skill: the body carries the rules that apply to every
document and each resource carries the detail behind one of them, so a long playbook costs
its short form on every load and its long form only where it is needed.

Rendering happens here rather than at read time, because ``{{component:<slot>}}``
markers resolve against a per-run context (see :mod:`.engine`) and the agent must never
see the branches that do not apply to the case in front of it. Resources are written
verbatim: they are read by the agent's own decision rather than composed for it.
"""

import logging
from typing import Any, Dict, Iterable, Mapping, Optional

from baseapp_ai_langkit.deep_agents.skills.engine import render_skill
from baseapp_ai_langkit.deep_agents.skills.sources import SkillSource

logger = logging.getLogger(__name__)

#: Virtual-filesystem prefix the skills middleware mounts skills under.
SKILLS_ROOT = "/skills/"


def skill_md_path(skill_dir: str) -> str:
    """Virtual-filesystem path of a skill's SKILL.md, keyed by directory name."""
    return f"{SKILLS_ROOT}{skill_dir}/SKILL.md"


def skill_resource_path(skill_dir: str, relative: str) -> str:
    """Virtual-filesystem path of one supporting file inside a skill's folder."""
    return f"{SKILLS_ROOT}{skill_dir}/{relative}"


def build_skill_files(
    source: SkillSource,
    skill_names: Optional[Iterable[str]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the agent's virtual filesystem payload from a skill source.

    ``skill_names`` filters by skill **directory** name. ``None`` writes every skill
    the source has; an empty iterable writes none, which is how a surface runs
    deliberately skill-less and how a skill eval builds its ``without_skill`` arm.
    Filtering a skill out takes its supporting files with it, so an excluded skill
    leaves nothing readable behind.

    A fresh payload is built per call so the agent's own virtual-filesystem writes
    never leak across runs.
    """
    allowed = None if skill_names is None else {str(name) for name in skill_names}
    files: Dict[str, Any] = {}
    for skill in source.iter_skills():
        if allowed is not None and skill.name not in allowed:
            continue
        files[skill_md_path(skill.name)] = _file_data(
            render_skill(skill.template, skill.components, context or {})
        )
        for relative, content in (skill.resources or {}).items():
            files[skill_resource_path(skill.name, relative)] = _file_data(content)
    return files


def _file_data(content: str) -> Any:
    """Wrap rendered markdown in the shape deepagents' virtual filesystem expects.

    Imported lazily so this module stays importable on a host without ``deepagents``
    installed, matching the rest of the package.
    """
    from deepagents.backends.utils import create_file_data

    return create_file_data(content)
