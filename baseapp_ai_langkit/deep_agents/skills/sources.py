"""Where a deep agent's skill playbooks come from.

The runtime only ever asks a source for "every skill you have right now", as a
directory name plus the SKILL.md text plus its parsed components plus its supporting
files. Everything about *where* those bytes live sits behind that one method, which is
what lets a project start with an in-repo folder and move to a separately-versioned
store later without touching the agent.

:class:`FilesystemSkillSource` is the only implementation shipped here: it reads a
directory on disk, with no fetching, no caching and no background writer. It covers
both the in-repo case and a bind-mounted working copy in local development.

A skill folder holds up to three kinds of file, and they differ in who decides that the
agent sees them::

    skills/case-context/
        SKILL.md                     # advertised up front, read when the agent decides
        components/petition.md       # spliced into SKILL.md at build time, by context
        rules/minors.md              # mounted beside SKILL.md, read on demand

``components/`` is composition: the run's context decides, before the agent starts, which
branches exist at all (see :mod:`.engine`). Everything else under the folder is a
**resource**: it is mounted on the virtual filesystem next to the SKILL.md, and the agent
reads one with ``read_file`` when its own reading of the document says it needs to. That
is what lets a SKILL.md stay short enough to load on every pass while the detail behind it
stays one tool call away.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, Protocol, Tuple, runtime_checkable

from baseapp_ai_langkit.deep_agents.skills.engine import SkillComponent, load_components

logger = logging.getLogger(__name__)

#: The playbook itself, which is never also a resource.
SKILL_MD = "SKILL.md"

#: Directories under a skill folder whose files are not resources. ``components`` is
#: composition-time only and must stay unreachable, or the agent could load a branch the
#: run's context excluded; ``__pycache__`` is never authored content.
NON_RESOURCE_DIRS = frozenset({"components", "__pycache__"})


def load_resources(skill_dir: Path) -> Dict[str, str]:
    """Every supporting file under a skill folder, keyed by its path relative to it.

    Recursive, so ``rules/minors.md`` arrives as ``"rules/minors.md"`` and lands at that
    path beside the SKILL.md. ``SKILL.md``, ``components/`` and dot-prefixed paths are
    excluded (see the module docstring for why the first two are).

    A file that cannot be read as UTF-8 text (a binary asset, a bad encoding, a
    permissions problem) is skipped with the error logged rather than raised: one
    unreadable file must not cost the skill or the agent build, which is the same
    contract :func:`~.engine.load_components` holds for a malformed component.
    """
    resources: Dict[str, str] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if relative.as_posix() == SKILL_MD or relative.parts[0] in NON_RESOURCE_DIRS:
            continue
        try:
            resources[relative.as_posix()] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.exception("Could not read skill resource %s; skipping", path)
    return resources


@dataclass(frozen=True)
class SkillDocument:
    """One skill as the runtime sees it, before rendering."""

    #: The skill's directory name, which is also how a caller selects it and how the
    #: trace reports that it was loaded.
    name: str
    #: The raw SKILL.md text, possibly carrying ``{{component:<slot>}}`` markers.
    template: str
    components: Tuple[SkillComponent, ...] = ()
    #: Supporting files, keyed by their path relative to the skill folder. Mounted
    #: beside the SKILL.md and read by the agent on demand, never rendered: a
    #: ``{{component:<slot>}}`` marker in one is left as written.
    resources: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class SkillSource(Protocol):
    """Anything that can produce the current set of skills."""

    def iter_skills(self) -> Iterable[SkillDocument]:
        """Every skill available right now, in a stable order."""


class FilesystemSkillSource:
    """Reads ``<root>/*/SKILL.md`` from disk on every call.

    Reading per run rather than caching is deliberate: an engineer editing a skill in
    a bind-mounted checkout sees the change on the next run with no restart, and the
    file set is tiny next to the cost of a model call.

    A missing or empty root is not an error. It means the agent runs with no skill
    playbooks, which is a supported configuration and the default before any skill is
    written.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def iter_skills(self) -> Iterable[SkillDocument]:
        if not self.root.is_dir():
            logger.debug("Skills root %s does not exist; running with no skills.", self.root)
            return ()
        return tuple(
            SkillDocument(
                name=skill_md.parent.name,
                template=skill_md.read_text(encoding="utf-8"),
                components=load_components(skill_md.parent),
                resources=load_resources(skill_md.parent),
            )
            for skill_md in sorted(self.root.glob("*/SKILL.md"))
        )


class EmptySkillSource:
    """A source with no skills, for a surface that deliberately runs without them."""

    def iter_skills(self) -> Iterable[SkillDocument]:
        return ()
