"""Static-yet-dynamic skill composition.

A skill folder may carry a ``components/`` directory next to its SKILL.md::

    skills/case-context/
        SKILL.md                        # may contain {{component:<slot>}} markers
        components/
            document_type_petition.md

Each component is markdown opening with a YAML frontmatter header::

    ---
    conditions:
      document_type: petition   # value may also be a list (matches any of them)
    priority: 100               # higher renders first when several match a slot
    slot: document_type         # optional, defaults to the single condition key
    disabled: true              # optional, keep the file but never render it
    ---

    Petition-specific instructions...

The **slot** comes from the ``slot:`` key, or, when omitted, the single condition key
(here ``document_type``). The file name is only a label: it shows up in logs and breaks
ties when several components share a slot, but it never determines the slot.

Rendering happens at agent-build time against a *context* dict (e.g.
``{"document_type": "petition"}``). A component is injected at its slot's
``{{component:<slot>}}`` marker only when **all** of its conditions match the context;
slots with no matching component collapse to nothing. The agent therefore only ever
sees the text that applies to the active case, the SKILL.md stays static, and the
composition is dynamic.

Components are **composition-time only**: they are spliced into the SKILL.md text
before it reaches the agent and are never written to the virtual filesystem. The agent
cannot ``ls`` or load a component on its own; only whole SKILL.md files are
skill-discoverable.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<header>.*?)\n---\s*\n?", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"\{\{component:(?P<slot>[\w-]+)\}\}")

_SCALAR_TYPES = (str, int, float, bool)


def _normalize(value: object) -> str:
    """Fold a condition/context value to a comparable form (str, lowercased)."""
    return str(value).strip().lower()


def _parse_condition(key: object, value: object) -> Tuple[str, Tuple[str, ...]]:
    """Normalize one ``conditions:`` entry to ``(key, accepted values)``.

    Raises ValueError when the value isn't a scalar or a non-empty list of scalars
    (e.g. a nested mapping or ``null``): the component's applicability would be
    undefined, so the caller skips it.
    """
    values = value if isinstance(value, list) else [value]
    if not values or not all(isinstance(v, _SCALAR_TYPES) for v in values):
        raise ValueError(f"condition {key!r} must be a scalar or a list of scalars, got {value!r}")
    return str(key), tuple(_normalize(v) for v in values)


@dataclass(frozen=True)
class SkillComponent:
    """One conditional markdown fragment parsed from ``components/<name>.md``."""

    name: str  # file stem, for logging
    slot: str
    conditions: Tuple[Tuple[str, Tuple[str, ...]], ...]  # key -> accepted values
    priority: int
    body: str
    disabled: bool = False  # `disabled: true` keeps the file but never renders it

    def matches(self, context: Mapping[str, object]) -> bool:
        """True when every condition key is present in ``context`` with an accepted value."""
        return all(
            key in context and _normalize(context[key]) in accepted
            for key, accepted in self.conditions
        )


def parse_component(path: Path) -> Optional[SkillComponent]:
    """Parse one component file; return None (and log) when it is malformed.

    A component is unusable without a frontmatter header, a non-empty ``conditions``
    mapping, and a resolvable slot (explicit ``slot:`` or a single condition key).
    Malformed components are skipped rather than raised so one bad file cannot take
    every skill down at build time.
    """
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        logger.error("Skill component %s has no frontmatter header; skipping", path)
        return None

    try:
        header = yaml.safe_load(match.group("header")) or {}
    except yaml.YAMLError:
        logger.error("Skill component %s has invalid YAML frontmatter; skipping", path)
        return None

    conditions = header.get("conditions")
    if not isinstance(conditions, dict) or not conditions:
        logger.error("Skill component %s declares no conditions mapping; skipping", path)
        return None

    try:
        normalized = tuple(_parse_condition(key, value) for key, value in conditions.items())
    except ValueError as exc:
        logger.error("Skill component %s has an unparseable condition (%s); skipping", path, exc)
        return None

    try:
        priority = int(header.get("priority", 0))
    except (TypeError, ValueError):
        logger.error(
            "Skill component %s has a non-integer priority %r; skipping",
            path,
            header.get("priority"),
        )
        return None

    slot = header.get("slot")
    if slot is None:
        if len(normalized) != 1:
            logger.error(
                "Skill component %s has multiple conditions but no explicit slot; skipping",
                path,
            )
            return None
        slot = normalized[0][0]

    return SkillComponent(
        name=path.stem,
        slot=str(slot),
        conditions=normalized,
        priority=priority,
        body=text[match.end() :].strip(),
        disabled=bool(header.get("disabled", False)),
    )


def load_components(skill_dir: Path, include_disabled: bool = False) -> Tuple[SkillComponent, ...]:
    """Parse every ``components/*.md`` under a skill folder (sorted, skips bad files).

    Any failure (malformed frontmatter, unparseable condition, even an unreadable file)
    drops only that component, with the error logged, never the skill or the agent
    build. Components marked ``disabled: true`` are excluded unless ``include_disabled``
    is set, which guardrail tests use to validate disabled files without rendering them.
    """
    components_dir = skill_dir / "components"
    if not components_dir.is_dir():
        return ()
    components = []
    for path in sorted(components_dir.glob("*.md")):
        try:
            component = parse_component(path)
        except Exception:  # noqa: BLE001 - one bad component must not break the build
            logger.exception("Failed to parse skill component %s; skipping", path)
            continue
        if component is None:
            continue
        if component.disabled and not include_disabled:
            logger.info("Skill component %s is disabled; skipping", path)
            continue
        components.append(component)
    return tuple(components)


def render_skill(
    template: str,
    components: Tuple[SkillComponent, ...],
    context: Mapping[str, object],
) -> str:
    """Replace each ``{{component:<slot>}}`` with its matching components' bodies.

    Matches for a slot are concatenated highest-priority first (file name as tiebreak);
    a slot with no match collapses to an empty string. Runs of blank lines left behind
    by collapsed slots are squashed so the rendered markdown stays tidy.
    """

    def _fill(match: "re.Match[str]") -> str:
        slot = match.group("slot")
        chosen = sorted(
            (c for c in components if c.slot == slot and c.matches(context)),
            key=lambda c: (-c.priority, c.name),
        )
        return "\n\n".join(c.body for c in chosen)

    rendered = PLACEHOLDER_RE.sub(_fill, template)
    return re.sub(r"\n{3,}", "\n\n", rendered)
