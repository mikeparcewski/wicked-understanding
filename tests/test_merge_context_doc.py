"""Tests for repo-orient/scripts/merge_context_doc.py — the merge MUST never
clobber hand-written content and MUST be idempotent (one managed block, ever)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills" / "repo-orient" / "scripts" / "merge_context_doc.py"
)
START = "<!-- wicked-understanding:context:start -->"
END = "<!-- wicked-understanding:context:end -->"


def run_merge(target: Path, content: str) -> str:
    """Write `content` to a temp file, run the merge into `target`, return stdout."""
    cf = target.parent / "_block.md"
    cf.write_text(content, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--target", str(target), "--content-file", str(cf)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def run_merge_raw(target: Path, content: str, *extra) -> subprocess.CompletedProcess:
    """Run the merge with arbitrary extra args; return the CompletedProcess.

    Unlike run_merge, does NOT assert success — used to exercise the
    --verify-routes failure path (non-zero exit, target left unwritten).
    """
    cf = target.parent / "_block.md"
    cf.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--target", str(target),
         "--content-file", str(cf), *[str(a) for a in extra]],
        capture_output=True, text=True,
    )


class TestMergeContextDoc(unittest.TestCase):
    def test_creates_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "CLAUDE.md"
            out = run_merge(target, "## Orientation\nrouting table here")
            text = target.read_text()
            self.assertIn("created", out)
            self.assertIn(START, text)
            self.assertIn(END, text)
            self.assertIn("routing table here", text)

    def test_appends_and_preserves_handwritten(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "CLAUDE.md"
            handwritten = "# My Project Rules\n\nNever delete prod. Use tabs.\n"
            target.write_text(handwritten, encoding="utf-8")
            run_merge(target, "## Orientation\nblock v1")
            text = target.read_text()
            # hand-written content survives verbatim
            self.assertIn("Never delete prod. Use tabs.", text)
            self.assertIn("# My Project Rules", text)
            # block added
            self.assertIn("block v1", text)
            self.assertEqual(text.count(START), 1)

    def test_replace_is_idempotent_no_duplication(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "CLAUDE.md"
            target.write_text("# Mine\nkeep me\n", encoding="utf-8")
            run_merge(target, "## Orientation\nblock v1")
            run_merge(target, "## Orientation\nblock v2 NEW")
            text = target.read_text()
            # exactly one managed block after two runs
            self.assertEqual(text.count(START), 1)
            self.assertEqual(text.count(END), 1)
            # refreshed to new content, old gone, hand-written preserved
            self.assertIn("block v2 NEW", text)
            self.assertNotIn("block v1", text)
            self.assertIn("keep me", text)

    def test_content_with_backslashes_is_literal(self):
        # regex-replacement backrefs (\1) in content must not be interpreted
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "AGENTS.md"
            run_merge(target, r"path: C:\Users\x  ref: \1 \g<0>")
            text = target.read_text()
            self.assertIn(r"C:\Users\x", text)
            self.assertIn(r"\1 \g<0>", text)


class TestVerifyRoutes(unittest.TestCase):
    """`--verify-routes` is a pre-write dead-link guard: every routed skill
    (`{slug}-fix-bug`) and wiki ref (`refs/arch.md`) in the body must resolve
    under the generated package dir, or the merge aborts WITHOUT writing."""

    @staticmethod
    def _fake_package(root: Path) -> Path:
        """A generated-skills dir with one task skill + one wiki ref present."""
        pkg = root / "skills"
        (pkg / "acme-fix-bug").mkdir(parents=True)
        (pkg / "acme-wiki" / "refs").mkdir(parents=True)
        (pkg / "acme-wiki" / "refs" / "arch.md").write_text("# arch\n", encoding="utf-8")
        return pkg

    ROUTING_OK = (
        "## Orientation\n\n"
        "| When you're… | Load |\n|---|---|\n"
        "| Fixing a bug | `acme-fix-bug` |\n"
        "| Understanding the architecture | `acme-wiki` → `refs/arch.md` |\n"
        "Run `npm test`; nullable cols use `null`.\n"  # prose backticks: must be ignored
    )

    def test_verify_routes_pass_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pkg = self._fake_package(d)
            target = d / "CLAUDE.md"
            r = run_merge_raw(target, self.ROUTING_OK, "--verify-routes", pkg)
            self.assertEqual(r.returncode, 0, r.stderr)
            # success line reports counts; prose backticks did NOT inflate them
            self.assertIn("verify-routes: 2 skill(s) + 1 ref(s) OK", r.stdout)
            self.assertTrue(target.exists())
            text = target.read_text()
            self.assertIn("acme-fix-bug", text)
            self.assertIn("refs/arch.md", text)
            self.assertEqual(text.count(START), 1)

    def test_verify_routes_fail_names_both_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pkg = self._fake_package(d)  # has acme-fix-bug + refs/arch.md ...
            target = d / "CLAUDE.md"
            content = (
                "## Orientation\n\n"
                "| Fixing a bug | `acme-fix-bug` |\n"          # resolves → sibling guard armed
                "| Writing tests | `acme-write-tests` |\n"     # dir absent → dead skill
                "| Domain | `acme-wiki` → `refs/ghost.md` |\n"  # ref absent → dead ref
            )
            r = run_merge_raw(target, content, "--verify-routes", pkg)
            self.assertNotEqual(r.returncode, 0)
            # both dead links surfaced on stderr
            self.assertIn("acme-write-tests", r.stderr)
            self.assertIn("refs/ghost.md", r.stderr)
            # the LIVE routes are NOT reported as dead
            self.assertNotIn("acme-fix-bug", r.stderr)
            # nothing written — pipeline catches the stale package before mutating the doc
            self.assertFalse(target.exists())

    def test_verify_routes_preserves_handwritten_on_failure(self):
        # A pre-existing hand-written doc must survive a failed verify untouched.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pkg = self._fake_package(d)
            target = d / "CLAUDE.md"
            handwritten = "# My Rules\n\nNever delete prod.\n"
            target.write_text(handwritten, encoding="utf-8")
            content = "| Fixing a bug | `acme-fix-bug` |\n| Tests | `acme-write-tests` |\n"
            r = run_merge_raw(target, content, "--verify-routes", pkg)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(target.read_text(), handwritten)  # byte-for-byte intact
            self.assertNotIn(START, target.read_text())

    def test_verify_routes_no_package_dir_does_not_nuke(self):
        # Verified against a dir with NO generated package: nothing resolves, so
        # the sibling guard suppresses skill reports and the merge still writes.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            empty = d / "skills"
            empty.mkdir()
            target = d / "CLAUDE.md"
            r = run_merge_raw(target, self.ROUTING_OK, "--verify-routes", empty)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("0 skill(s) + 0 ref(s) OK", r.stdout)
            self.assertTrue(target.exists())

    def test_verify_routes_missing_dir_errors(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            target = d / "CLAUDE.md"
            r = run_merge_raw(target, self.ROUTING_OK, "--verify-routes", d / "nope")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not found", r.stderr)
            self.assertFalse(target.exists())


class TestTargetAgnostic(unittest.TestCase):
    """The merge is target-agnostic: the same block lands cleanly in AGENTS.md
    AND GEMINI.md (not just CLAUDE.md), each a valid single managed block."""

    def test_merges_into_agents_and_gemini(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            body = "## Orientation\n\n| Fixing a bug | `acme-fix-bug` |\n"
            for name in ("AGENTS.md", "GEMINI.md"):
                target = d / name
                out = run_merge(target, body)
                text = target.read_text()
                self.assertIn("created", out)
                self.assertEqual(text.count(START), 1, name)
                self.assertEqual(text.count(END), 1, name)
                self.assertIn("acme-fix-bug", text)
                # re-running refreshes in place (still exactly one block)
                run_merge(target, "## Orientation\n\n| Adding | `acme-add-feature` |\n")
                text2 = target.read_text()
                self.assertEqual(text2.count(START), 1, name)
                self.assertIn("acme-add-feature", text2)
                self.assertNotIn("acme-fix-bug", text2)


if __name__ == "__main__":
    unittest.main()
