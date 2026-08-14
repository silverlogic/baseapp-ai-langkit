"""Unit tests for skill composition, sources and the virtual-filesystem payload."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from baseapp_ai_langkit.deep_agents.skills import engine
from baseapp_ai_langkit.deep_agents.skills.engine import (
    load_components,
    parse_component,
    render_skill,
)
from baseapp_ai_langkit.deep_agents.skills.files import (
    build_skill_files,
    skill_md_path,
    skill_resource_path,
)
from baseapp_ai_langkit.deep_agents.skills import sources as sources_module
from baseapp_ai_langkit.deep_agents.skills.sources import (
    EmptySkillSource,
    FilesystemSkillSource,
    SkillDocument,
    load_resources,
)


class _SkillTree:
    """A throwaway skills root on disk."""

    def __init__(self, stack) -> None:
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))

    def skill(self, name: str, body: str) -> Path:
        directory = self.root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(body, encoding="utf-8")
        return directory

    def component(self, skill: str, filename: str, body: str) -> Path:
        components = self.root / skill / "components"
        components.mkdir(parents=True, exist_ok=True)
        path = components / filename
        path.write_text(body, encoding="utf-8")
        return path

    def resource(self, skill: str, relative: str, body: str) -> Path:
        path = self.root / skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path


def _tree(case: SimpleTestCase) -> _SkillTree:
    import contextlib

    stack = contextlib.ExitStack()
    case.addCleanup(stack.close)
    return _SkillTree(stack)


COMPONENT = """---
conditions:
  document_type: petition
priority: 10
---

Petition text.
"""


class ParseComponentTests(SimpleTestCase):
    def test_parses_a_well_formed_component(self):
        tree = _tree(self)
        tree.skill("case-header", "body")
        path = tree.component("case-header", "document_type_petition.md", COMPONENT)
        component = parse_component(path)
        self.assertEqual(component.slot, "document_type")
        self.assertEqual(component.priority, 10)
        self.assertEqual(component.body, "Petition text.")
        self.assertTrue(component.matches({"document_type": "Petition"}))
        self.assertFalse(component.matches({"document_type": "order"}))
        self.assertFalse(component.matches({}))

    def test_a_list_condition_matches_any_value(self):
        tree = _tree(self)
        tree.skill("s", "body")
        path = tree.component("s", "c.md", "---\nconditions:\n  kind: [a, b]\n---\n\ntext\n")
        component = parse_component(path)
        self.assertTrue(component.matches({"kind": "b"}))
        self.assertFalse(component.matches({"kind": "c"}))

    def test_an_explicit_slot_wins_over_the_condition_key(self):
        tree = _tree(self)
        tree.skill("s", "body")
        path = tree.component(
            "s", "c.md", "---\nconditions:\n  kind: a\nslot: intro\n---\n\ntext\n"
        )
        self.assertEqual(parse_component(path).slot, "intro")

    def test_malformed_components_are_skipped_not_raised(self):
        tree = _tree(self)
        tree.skill("s", "body")
        cases = {
            "no_frontmatter.md": "just text\n",
            "bad_yaml.md": "---\nconditions: [\n---\n\ntext\n",
            "no_conditions.md": "---\npriority: 1\n---\n\ntext\n",
            "nested_condition.md": "---\nconditions:\n  kind:\n    nested: 1\n---\n\ntext\n",
            "bad_priority.md": "---\nconditions:\n  kind: a\npriority: high\n---\n\ntext\n",
            "no_slot.md": "---\nconditions:\n  a: 1\n  b: 2\n---\n\ntext\n",
        }
        for filename, body in cases.items():
            path = tree.component("s", filename, body)
            with self.subTest(filename=filename):
                with self.assertLogs(engine.logger, level="ERROR"):
                    self.assertIsNone(parse_component(path))


class LoadComponentsTests(SimpleTestCase):
    def test_no_components_directory_yields_nothing(self):
        tree = _tree(self)
        self.assertEqual(load_components(tree.skill("s", "body")), ())

    def test_disabled_components_are_excluded_by_default(self):
        tree = _tree(self)
        directory = tree.skill("s", "body")
        tree.component("s", "c.md", "---\nconditions:\n  kind: a\ndisabled: true\n---\n\ntext\n")
        with self.assertLogs(engine.logger, level="INFO"):
            self.assertEqual(load_components(directory), ())
        self.assertEqual(len(load_components(directory, include_disabled=True)), 1)

    def test_one_bad_component_does_not_drop_the_good_one(self):
        tree = _tree(self)
        directory = tree.skill("s", "body")
        tree.component("s", "bad.md", "no frontmatter\n")
        tree.component("s", "good.md", COMPONENT)
        with self.assertLogs(engine.logger, level="ERROR"):
            components = load_components(directory)
        self.assertEqual([c.name for c in components], ["good"])


class RenderSkillTests(SimpleTestCase):
    def _component(self, slot: str, body: str, priority: int = 0):
        tree = _tree(self)
        tree.skill("s", "body")
        path = tree.component(
            "s",
            f"{slot}_{priority}_{body}.md",
            f"---\nconditions:\n  {slot}: alpha\npriority: {priority}\n---\n\n{body}\n",
        )
        return parse_component(path)

    def test_matching_components_are_spliced_highest_priority_first(self):
        components = (
            self._component("kind", "low", priority=1),
            self._component("kind", "high", priority=9),
        )
        rendered = render_skill("intro\n\n{{component:kind}}\n\nend", components, {"kind": "alpha"})
        self.assertEqual(rendered, "intro\n\nhigh\n\nlow\n\nend")

    def test_an_unmatched_slot_collapses(self):
        components = (self._component("kind", "text"),)
        rendered = render_skill("intro\n\n{{component:kind}}\n\nend", components, {})
        self.assertEqual(rendered, "intro\n\nend")

    def test_a_template_with_no_markers_is_returned_as_is(self):
        self.assertEqual(render_skill("plain", (), {}), "plain")


class LoadResourcesTests(SimpleTestCase):
    def test_a_skill_with_only_a_playbook_has_no_resources(self):
        tree = _tree(self)
        self.assertEqual(load_resources(tree.skill("s", "body")), {})

    def test_supporting_files_are_keyed_by_their_relative_path(self):
        tree = _tree(self)
        directory = tree.skill("s", "body")
        tree.resource("s", "rules/minors.md", "minor text")
        tree.resource("s", "reference.md", "reference text")
        self.assertEqual(
            load_resources(directory),
            {"reference.md": "reference text", "rules/minors.md": "minor text"},
        )

    def test_the_playbook_components_and_dotfiles_are_not_resources(self):
        tree = _tree(self)
        directory = tree.skill("s", "body")
        tree.component("s", "c.md", COMPONENT)
        tree.resource("s", ".hidden/notes.md", "hidden")
        tree.resource("s", ".DS_Store", "junk")
        self.assertEqual(load_resources(directory), {})

    def test_an_undecodable_file_is_skipped_not_raised(self):
        tree = _tree(self)
        directory = tree.skill("s", "body")
        (directory / "logo.png").write_bytes(b"\xff\xfe\x00binary")
        tree.resource("s", "rules/good.md", "good")
        with self.assertLogs(sources_module.logger, level="ERROR"):
            self.assertEqual(load_resources(directory), {"rules/good.md": "good"})


class FilesystemSkillSourceTests(SimpleTestCase):
    def test_a_missing_root_means_no_skills(self):
        source = FilesystemSkillSource(Path("/nonexistent/skills"))
        self.assertEqual(list(source.iter_skills()), [])

    def test_an_empty_root_means_no_skills(self):
        tree = _tree(self)
        self.assertEqual(list(FilesystemSkillSource(tree.root).iter_skills()), [])

    def test_reads_every_skill_with_its_components_and_resources(self):
        tree = _tree(self)
        tree.skill("case-header", "header {{component:document_type}}")
        tree.component("case-header", "document_type_petition.md", COMPONENT)
        tree.resource("case-header", "rules/venue.md", "venue text")
        tree.skill("deals", "deals")
        skills = list(FilesystemSkillSource(tree.root).iter_skills())
        self.assertEqual([s.name for s in skills], ["case-header", "deals"])
        self.assertEqual(len(skills[0].components), 1)
        self.assertEqual(skills[0].resources, {"rules/venue.md": "venue text"})
        self.assertEqual(skills[1].resources, {})

    def test_a_later_edit_is_picked_up_without_a_restart(self):
        tree = _tree(self)
        tree.skill("deals", "first")
        source = FilesystemSkillSource(tree.root)
        self.assertEqual(list(source.iter_skills())[0].template, "first")
        tree.skill("deals", "second")
        self.assertEqual(list(source.iter_skills())[0].template, "second")


class BuildSkillFilesTests(SimpleTestCase):
    class _Source:
        def __init__(self, *skills):
            self.skills = skills

        def iter_skills(self):
            return self.skills

    def test_every_skill_becomes_a_virtual_file(self):
        source = self._Source(SkillDocument("deals", "deal text"))
        files = build_skill_files(source)
        self.assertEqual(list(files), [skill_md_path("deals")])

    def test_skill_names_filter_the_payload(self):
        source = self._Source(SkillDocument("deals", "a"), SkillDocument("header", "b"))
        self.assertEqual(
            list(build_skill_files(source, skill_names=["header"])), [skill_md_path("header")]
        )
        self.assertEqual(build_skill_files(source, skill_names=[]), {})
        self.assertEqual(len(build_skill_files(source, skill_names=None)), 2)

    def test_an_empty_source_produces_an_empty_payload(self):
        self.assertEqual(build_skill_files(EmptySkillSource()), {})

    def test_components_are_rendered_and_never_written_as_files(self):
        tree = _tree(self)
        tree.skill("case-header", "header\n\n{{component:document_type}}")
        tree.component("case-header", "document_type_petition.md", COMPONENT)
        files = build_skill_files(
            FilesystemSkillSource(tree.root), context={"document_type": "petition"}
        )
        self.assertEqual(list(files), [skill_md_path("case-header")])
        content = files[skill_md_path("case-header")]["content"]
        self.assertIn("Petition text.", content)

    def test_a_fresh_payload_is_built_per_call(self):
        source = self._Source(SkillDocument("deals", "a"))
        self.assertIsNot(build_skill_files(source), build_skill_files(source))

    def test_supporting_files_are_mounted_beside_the_playbook(self):
        tree = _tree(self)
        tree.skill("contacts", "body")
        tree.resource("contacts", "rules/minors.md", "minor text")
        files = build_skill_files(FilesystemSkillSource(tree.root))
        path = skill_resource_path("contacts", "rules/minors.md")
        self.assertEqual(sorted(files), sorted([skill_md_path("contacts"), path]))
        self.assertEqual(files[path]["content"], "minor text")

    def test_a_resource_is_written_verbatim_and_never_rendered(self):
        source = self._Source(
            SkillDocument("s", "body", resources={"rules/r.md": "{{component:kind}} kept"})
        )
        files = build_skill_files(source, context={"kind": "alpha"})
        self.assertEqual(
            files[skill_resource_path("s", "rules/r.md")]["content"], "{{component:kind}} kept"
        )

    def test_filtering_a_skill_out_drops_its_supporting_files_too(self):
        tree = _tree(self)
        tree.skill("contacts", "body")
        tree.resource("contacts", "rules/minors.md", "minor text")
        tree.skill("deals", "body")
        files = build_skill_files(FilesystemSkillSource(tree.root), skill_names=["deals"])
        self.assertEqual(list(files), [skill_md_path("deals")])
