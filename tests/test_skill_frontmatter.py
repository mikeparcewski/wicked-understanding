"""Guard our OWN skill package against the two bug classes that made `npx skills`
silently drop skills:
  1. colon-namespaced / non-conforming `name` (must be lowercase/digits/hyphens AND equal the folder)
  2. a PLAIN `description:` scalar containing ": " (breaks the real CLI's YAML parser)
These are offline checks (no network) mirroring what the real tool enforces.
"""

import re
import unittest
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
NAME_RE = re.compile(r"^[a-z0-9-]+$")


def frontmatter(path: Path) -> dict:
    """Return {'name':..., 'desc_is_block':bool, 'desc_value':str} from a SKILL.md."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0].strip() == "---", f"{path}: no frontmatter"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fm = lines[1:end]
    name = ""
    desc_is_block = False
    desc_value_parts = []
    i = 0
    while i < len(fm):
        line = fm[i]
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            rest = line.split(":", 1)[1].strip()
            if rest in (">", "|", ">-", "|-", ">+", "|+"):
                desc_is_block = True
                # block body = following more-indented lines (not checked for ": ")
            else:
                desc_value_parts.append(rest)
                # gather plain-scalar continuation lines (indented, not a new key)
                j = i + 1
                while j < len(fm) and (fm[j].startswith((" ", "\t")) and ":" not in fm[j].split("#")[0][:40]):
                    desc_value_parts.append(fm[j].strip())
                    j += 1
        i += 1
    return {"name": name, "desc_is_block": desc_is_block, "desc_value": " ".join(desc_value_parts)}


class TestSkillFrontmatter(unittest.TestCase):
    def setUp(self):
        self.skills = sorted(p for p in SKILLS_DIR.glob("*/SKILL.md"))
        self.assertTrue(self.skills, "no skills found")

    def test_name_equals_folder_and_is_agentskills_valid(self):
        for sk in self.skills:
            fm = frontmatter(sk)
            folder = sk.parent.name
            self.assertEqual(fm["name"], folder, f"{sk}: name '{fm['name']}' != folder '{folder}'")
            self.assertRegex(fm["name"], NAME_RE, f"{sk}: name not lowercase/digits/hyphens (no colon!)")

    def test_description_has_no_plain_scalar_colon_space(self):
        # A plain (non-block) description containing ": " breaks the real npx-skills
        # YAML parser → the skill is silently dropped. Block scalars (>, |) are safe.
        for sk in self.skills:
            fm = frontmatter(sk)
            if not fm["desc_is_block"]:
                self.assertNotIn(
                    ": ", fm["desc_value"],
                    f"{sk}: plain description contains ': ' — use a folded block scalar "
                    f"(description: >) or npx skills will drop this skill",
                )


if __name__ == "__main__":
    unittest.main()
