"""
Tests for skills/repo-wiki-planner/scripts/generate_viewer.py.

Fixture: a {repo}-wiki skill dir with refs/ holding two minimal articles.
Run the script and assert:
  - it exits 0 and writes the output HTML
  - the file is self-contained and non-trivial (> 1 KB)
  - both articles surface: their on-disk stems (article ids) AND their
    frontmatter slugs are embedded in the page
  - the repo name (derived by stripping `-wiki`) appears in the title chrome
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import _support

FIXTURE_SKILL = _support.FIXTURES_DIR / "viewer-skill"

# (stem == article id, frontmatter slug) for each fixture article.
ARTICLES = [
    ("overview", "acme-payments-overview"),
    ("cap-charge-capture", "acme-payments-cap-charge-capture"),
]


class TestGenerateViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        # Copy the fixture skill into the tempdir so we never write into the repo.
        cls.skill_dir = tmp / "acme-payments-wiki"
        shutil.copytree(FIXTURE_SKILL, cls.skill_dir)
        cls.output = tmp / "viewer.html"

        cls.result = _support.run_script(
            _support.VIEWER_SCRIPT,
            "--skill-dir", cls.skill_dir,
            "--output", cls.output,
        )
        cls.html = cls.output.read_text(encoding="utf-8") if cls.output.exists() else ""

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_script_succeeded(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_output_exists_and_nontrivial(self):
        self.assertTrue(self.output.exists(), "viewer HTML not written")
        size = self.output.stat().st_size
        self.assertGreater(size, 1024, f"viewer HTML is only {size} bytes (expected > 1KB)")

    def test_is_html_document(self):
        self.assertTrue(self.html.lstrip().startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", self.html)

    def test_both_article_stems_present(self):
        for stem, _slug in ARTICLES:
            self.assertIn(stem, self.html, f"article id/stem {stem!r} missing from viewer")

    def test_both_article_slugs_present(self):
        for _stem, slug in ARTICLES:
            self.assertIn(slug, self.html, f"article slug {slug!r} missing from viewer")

    def test_article_count_reflects_two(self):
        # The viewer prints "... N articles" to stdout and renders a count chip.
        self.assertIn("2 articles", self.html)

    def test_repo_name_in_chrome(self):
        # get_repo_name strips "-wiki" and title-cases -> "Acme Payments".
        self.assertIn("Acme Payments", self.html)


if __name__ == "__main__":
    unittest.main()
