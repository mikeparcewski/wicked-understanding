"""
Tests for skills/repo-analyst/scripts/check_freshness.py.

Run entirely in a NON-git tempdir so the git-based path is unavailable and the
script falls back to its mtime comparison (the branch under test). Cases:
  (a) no manifest present              -> status "missing"
  (b) artifact + manifest, mtimes match -> status "fresh"
  (c) tracked file mtime bumped +2s     -> status "stale"

JSON stdout is parsed and asserted.

Watch-pattern note: mtime_check also flags *new* files matching a watch pattern.
We deliberately use patterns whose cleaned form still contains a glob ("src/**")
or points at a path that does not exist, so that branch never fires spuriously —
the test isolates the mtime comparison.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import _support


def write_manifest(artifacts_dir, lens, files_analyzed, watch_patterns=None, generated_at="2026-01-01T00:00:00+00:00"):
    """Write a minimal but schema-shaped manifest sidecar for one lens.

    No git_commit key -> the script cannot use the git path even if it wanted to,
    guaranteeing the mtime fallback.
    """
    manifest = {
        "lens": lens,
        "generated_at": generated_at,
        "watch_patterns": watch_patterns if watch_patterns is not None else ["src/**"],
        "files_analyzed": files_analyzed,
    }
    (artifacts_dir / f"{lens}.manifest.json").write_text(json.dumps(manifest, indent=2))


class TestCheckFreshness(unittest.TestCase):
    def setUp(self):
        # System tempdir is not inside any git repo -> mtime fallback path.
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        self.artifacts = self.tmp / "artifacts"
        self.repo.mkdir()
        self.artifacts.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, lens="domain"):
        result = _support.run_script(
            _support.FRESHNESS_SCRIPT,
            "--repo-root", self.repo,
            "--artifacts-dir", self.artifacts,
            "--lenses", lens,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        return data

    def test_missing_when_no_manifest(self):
        data = self._run("domain")
        self.assertIn("domain", data)
        self.assertEqual(data["domain"]["status"], "missing", data["domain"])

    def test_fresh_when_mtimes_match(self):
        # Create a source file and record its real mtime in the manifest.
        src = self.repo / "model.py"
        src.write_text("class Order: ...\n")
        mtime = src.stat().st_mtime

        write_manifest(
            self.artifacts,
            "domain",
            files_analyzed=[{"path": "model.py", "mtime": mtime, "size_bytes": src.stat().st_size}],
            # Glob-containing pattern -> the "new file" probe is skipped, so the
            # result is decided purely by mtime equality.
            watch_patterns=["src/**"],
        )

        data = self._run("domain")
        self.assertEqual(
            data["domain"]["status"], "fresh",
            f"expected fresh, got {data['domain']}"
        )
        self.assertIn("mtime fallback", data["domain"]["reason"])

    def test_stale_when_file_modified(self):
        src = self.repo / "model.py"
        src.write_text("class Order: ...\n")
        original_mtime = src.stat().st_mtime

        write_manifest(
            self.artifacts,
            "domain",
            files_analyzed=[{"path": "model.py", "mtime": original_mtime, "size_bytes": src.stat().st_size}],
            watch_patterns=["src/**"],
        )

        # Bump the file mtime well beyond the script's 1.0s tolerance.
        new_mtime = original_mtime + 2.0
        os.utime(src, (new_mtime, new_mtime))

        data = self._run("domain")
        self.assertEqual(
            data["domain"]["status"], "stale",
            f"expected stale after mtime bump, got {data['domain']}"
        )

    def test_stale_when_tracked_file_deleted(self):
        src = self.repo / "model.py"
        src.write_text("class Order: ...\n")
        mtime = src.stat().st_mtime
        write_manifest(
            self.artifacts,
            "domain",
            files_analyzed=[{"path": "model.py", "mtime": mtime, "size_bytes": src.stat().st_size}],
            watch_patterns=["src/**"],
        )
        src.unlink()

        data = self._run("domain")
        self.assertEqual(data["domain"]["status"], "stale", data["domain"])
        self.assertIn("deleted", data["domain"]["reason"])

    def test_missing_artifacts_dir_reports_all_missing(self):
        """If the artifacts dir itself is absent, every lens is 'missing'."""
        ghost = self.tmp / "does-not-exist"
        result = _support.run_script(
            _support.FRESHNESS_SCRIPT,
            "--repo-root", self.repo,
            "--artifacts-dir", ghost,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        for lens in ("survey", "architecture", "domain", "technical", "ops"):
            self.assertEqual(data[lens]["status"], "missing", f"{lens}: {data[lens]}")


if __name__ == "__main__":
    unittest.main()
