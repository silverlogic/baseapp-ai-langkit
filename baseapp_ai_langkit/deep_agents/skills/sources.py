"""Where a deep agent's skill playbooks come from.

The runtime only ever asks a source for "every skill you have right now", as a
directory name plus the SKILL.md text plus its parsed components. Everything about
*where* those bytes live sits behind that one method, which is what lets a project
start with an in-repo folder and move to a separately-versioned store later without
touching the agent.

:class:`FilesystemSkillSource` is the only implementation shipped here: it reads a
directory on disk, with no fetching, no caching and no background writer. It covers
both the in-repo case and a bind-mounted working copy in local development.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Tuple, runtime_checkable

from baseapp_ai_langkit.deep_agents.skills.engine import SkillComponent, load_components

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillDocument:
    """One skill as the runtime sees it, before rendering."""

    #: The skill's directory name, which is also how a caller selects it and how the
    #: trace reports that it was loaded.
    name: str
    #: The raw SKILL.md text, possibly carrying ``{{component:<slot>}}`` markers.
    template: str
    components: Tuple[SkillComponent, ...] = ()


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
            )
            for skill_md in sorted(self.root.glob("*/SKILL.md"))
        )


class EmptySkillSource:
    """A source with no skills, for a surface that deliberately runs without them."""

    def iter_skills(self) -> Iterable[SkillDocument]:
        return ()
