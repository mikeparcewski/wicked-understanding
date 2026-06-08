"""
Regression guard for skills/repo-wiki-planner/scripts/assemble_wiki_skill.py.

These assertions lock in bugs that were fixed and must not regress:

  1. Skill name is PER-REPO (`acme-payments-wiki`), not the literal
     `wicked-understanding:wiki`. A shared name collides across repos and breaks
     the viewer's get_repo_name() (which strips the `-wiki` suffix).

  2. Links are driven by each plan article's `ref_file` — NEVER a hardcoded
     filename. Every ``refs/...md`` link in the Load guide must correspond to a
     plan article's ref_file, prefixed `refs/`. The fixture's api-reference uses
     ref_file `mcp-tools.md`, so `refs/mcp-tools.md` MUST appear and the old
     hardcoded `refs/api.md` MUST be absent.

  3. Key entities table is populated from the domain lens's `### H3` "Core
     Entities" blocks. It must contain the real entity names (Charge, Merchant,
     LedgerEntry) — not the literal placeholder `(see refs/overview.md)`, and the
     `| Entity |` token must only be the table HEADER, never a data row.

  4. The description uses correct singular/plural ("1 capability deep-dive", no
     trailing "s") and shows no obvious mid-word truncation.

The fixture domain.md uses the exact repo-domain-analyst format: a
`## Core Entities` section of `### Name` blocks each with a
`- **Represents**: ...` bullet.
"""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import _support

FIXTURES = _support.FIXTURES_DIR / "assembler"

# ref_files declared in the fixture plan (single source of truth for links).
EXPECTED_REF_FILES = {
    "overview.md",
    "arch.md",
    "mcp-tools.md",
    "onboard.md",
    "cap-charge-capture.md",
}
ENTITY_NAMES = ["Charge", "Merchant", "LedgerEntry"]


def extract_description(skill_text):
    """Return the YAML `description: >` folded block as a single string.

    The assembler writes:
        description: >
          <line 1>
          <line 2>
        generated: ...
    so we collect indented continuation lines until the next top-level key.
    """
    lines = skill_text.splitlines()
    out = []
    capturing = False
    for line in lines:
        if not capturing:
            if line.strip().startswith("description:"):
                capturing = True
            continue
        # Continuation lines are indented; a non-indented line ends the block.
        if line and not line[0].isspace():
            break
        out.append(line.strip())
    return " ".join(s for s in out if s)


class TestAssembleWikiSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)

        # Copy the lens artifacts into a working artifacts dir.
        artifacts = tmp / "artifacts"
        artifacts.mkdir()
        for name in ("survey.md", "domain.md", "ops.md"):
            shutil.copy(FIXTURES / name, artifacts / name)

        staging = tmp / "acme-payments-wiki"
        plan = FIXTURES / "wiki-plan.json"

        cls.result = _support.run_script(
            _support.ASSEMBLE_SCRIPT,
            "--plan-file", plan,
            "--skill-staging", staging,
            "--artifacts-dir", artifacts,
        )
        cls.skill_path = staging / "SKILL.md"
        cls.skill_text = cls.skill_path.read_text() if cls.skill_path.exists() else ""

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_script_succeeded(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertTrue(self.skill_path.exists(), "SKILL.md was not written")

    def test_name_is_per_repo(self):
        self.assertIn("name: acme-payments-wiki", self.skill_text)
        self.assertNotIn(
            "name: wicked-understanding:wiki",
            self.skill_text,
            "skill name regressed to the shared/colliding form",
        )

    def test_load_guide_links_match_plan_ref_files(self):
        # Every refs/<file>.md token anywhere in the SKILL.md must be one of the
        # plan's ref_files. This catches both a hardcoded filename and a typo.
        found = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        self.assertTrue(found, "no refs/*.md links found in SKILL.md")

        unexpected = found - EXPECTED_REF_FILES
        self.assertEqual(
            unexpected,
            set(),
            f"SKILL.md links to ref files not declared in the plan: {unexpected}",
        )

    def test_api_reference_uses_plan_ref_file_not_hardcoded(self):
        self.assertIn(
            "refs/mcp-tools.md",
            self.skill_text,
            "api-reference link did not honor the plan's ref_file (mcp-tools.md)",
        )
        self.assertNotIn(
            "refs/api.md",
            self.skill_text,
            "hardcoded refs/api.md link reappeared (the dead-link bug)",
        )

    def test_every_plan_ref_file_is_linked(self):
        found = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        missing = EXPECTED_REF_FILES - found
        self.assertEqual(missing, set(), f"plan ref files not linked in SKILL.md: {missing}")

    def test_key_entities_table_populated_from_h3_blocks(self):
        # The placeholder fallback must be gone, and real entity names present.
        self.assertNotIn(
            "(see refs/overview.md)",
            self.skill_text,
            "entities table fell back to the empty placeholder",
        )
        for name in ENTITY_NAMES:
            self.assertIn(
                f"`{name}`",
                self.skill_text,
                f"entity {name!r} (a ### H3 block) missing from the entities table",
            )

    def test_entity_header_present_but_not_as_data_row(self):
        # The string "Entity" should appear only as the column header
        # "| Entity | What it represents |", never as a scraped data row.
        entity_lines = [
            ln for ln in self.skill_text.splitlines()
            if re.search(r"\bEntity\b", ln)
        ]
        self.assertTrue(entity_lines, "expected an 'Entity' column header")
        for ln in entity_lines:
            self.assertIn(
                "What it represents",
                ln,
                f"'Entity' appeared outside the header row (scraped prose?): {ln!r}",
            )

    def test_description_singular_capability(self):
        desc = extract_description(self.skill_text)
        self.assertTrue(desc, "could not extract description block")
        self.assertIn(
            "1 capability deep-dive",
            desc,
            f"expected singular 'capability deep-dive'; description was: {desc!r}",
        )
        self.assertNotIn(
            "1 capability deep-dives",
            desc,
            "plural 's' bug on a single capability",
        )

    def test_description_has_no_obvious_midword_truncation(self):
        desc = extract_description(self.skill_text)
        # The full final sentence must be intact (no [:N] chop of the description).
        self.assertTrue(
            desc.rstrip().endswith("spread across dozens of files."),
            f"description appears truncated mid-sentence: ...{desc[-60:]!r}",
        )
        # The entity list embedded in the description must be whole.
        self.assertIn("Charge, Merchant, LedgerEntry", desc)
        # Sanity: it names the repo and stack, proving it is repo-specific.
        self.assertIn("acme-payments", desc)


class TestWikiSkillNameKebabCase(unittest.TestCase):
    """The generated frontmatter `name` must be a valid agentskills name:
    lowercase letters/numbers/hyphens only. A repo whose name contains an
    underscore (e.g. `acme_app`) must kebab-case to `acme-app-wiki`, NEVER
    `acme_app-wiki` — an underscore makes the name invalid and the skill won't
    install via `npx skills`.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)

        # Minimal artifacts — the assembler tolerates missing sections; the
        # name derivation only depends on plan["repo"], so an empty dir suffices.
        artifacts = tmp / "artifacts"
        artifacts.mkdir()

        # Inline plan with an underscore repo name and one article so the
        # assembler has a ref_file to render (exercises the full happy path).
        plan = {
            "repo": "acme_app",
            "stack": "Python",
            "type": "service",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "articles": [
                {
                    "type": "product-overview",
                    "slug": "acme_app-overview",
                    "ref_file": "overview.md",
                    "title": "Product Overview",
                    "audience": "both",
                    "priority": 1,
                    "source_artifacts": ["survey.md"],
                    "subject": "",
                }
            ],
        }
        plan_path = tmp / "acme_app-wiki-plan.json"
        plan_path.write_text(json.dumps(plan))

        staging = tmp / "acme-app-wiki"
        cls.result = _support.run_script(
            _support.ASSEMBLE_SCRIPT,
            "--plan-file", plan_path,
            "--skill-staging", staging,
            "--artifacts-dir", artifacts,
        )
        cls.skill_path = staging / "SKILL.md"
        cls.skill_text = cls.skill_path.read_text() if cls.skill_path.exists() else ""

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_underscore_repo_name_is_kebab_cased(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertIn(
            "name: acme-app-wiki",
            self.skill_text,
            "underscore repo name was not kebab-cased to acme-app-wiki",
        )
        self.assertNotIn(
            "name: acme_app-wiki",
            self.skill_text,
            "frontmatter `name` kept the underscore — invalid agentskills name",
        )


if __name__ == "__main__":
    unittest.main()
