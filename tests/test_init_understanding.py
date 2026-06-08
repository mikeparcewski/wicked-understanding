"""
Tests for skills/repo-analyst/scripts/init_understanding.py.

Covers:
  - normalize_remote_url consistency: https / git@ / trailing-slash / .git
    variants of the same repo all collapse to the key `github.com/o/r`.
    Asserted two ways: (1) directly via importlib, (2) end-to-end by pointing a
    real git repo's origin at each variant and reading the printed artifacts dir.
  - `init` creates the store dir and prints a path under the (hermetic) HOME.
  - `list` runs and reports the initialized repo.

All subprocess invocations pin HOME (and USERPROFILE on Windows) to a tempdir so
the real ~/.wicked-understanding store is never touched.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _support


EXPECTED_KEY = "github.com/o/r"
URL_VARIANTS = [
    "https://github.com/o/r.git",
    "https://github.com/o/r",
    "https://github.com/o/r/",
    "git@github.com:o/r.git",
    "git@github.com:o/r",
    "ssh://git@github.com/o/r.git",
]


class TestNormalizeRemoteUrlDirect(unittest.TestCase):
    """Direct unit check of the pure function via importlib."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _support.load_module(_support.INIT_SCRIPT, "init_understanding_under_test")

    def test_all_variants_normalize_to_same_key(self):
        keys = {self.mod.normalize_remote_url(u) for u in URL_VARIANTS}
        self.assertEqual(
            keys,
            {EXPECTED_KEY},
            f"URL variants normalized to differing keys: {keys}",
        )

    def test_key_is_exact(self):
        for url in URL_VARIANTS:
            self.assertEqual(self.mod.normalize_remote_url(url), EXPECTED_KEY, url)


def _git(repo_root, *args):
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestInitEndToEnd(unittest.TestCase):
    """Subprocess-level checks against the real CLI entry point."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.env = _support.hermetic_home_env(self.home)
        # Confirm git is usable; otherwise the remote-keyed path can't be tested.
        probe = subprocess.run(["git", "--version"], capture_output=True)
        self.have_git = probe.returncode == 0

    def tearDown(self):
        self._tmp.cleanup()

    def _init_repo_with_remote(self, url):
        _git(self.repo, "init")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "t")
        # Remove any pre-existing origin, then point it at the variant.
        _git(self.repo, "remote", "remove", "origin")
        res = _git(self.repo, "remote", "add", "origin", url)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_init_creates_store_and_prints_path(self):
        """`init` on a remote-less dir keys by dir name; store dir is created and printed."""
        result = _support.run_script(
            _support.INIT_SCRIPT, "init", "--repo-root", self.repo, env=self.env
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        printed = result.stdout.strip()
        self.assertTrue(printed, "init printed nothing")

        artifacts_dir = Path(printed)
        self.assertTrue(artifacts_dir.is_dir(), f"artifacts dir not created: {printed}")
        # Must live under the hermetic HOME, never the real store.
        self.assertIn(str(self.home), printed)
        self.assertIn(".wicked-understanding", printed)
        # meta.json + index.json written.
        self.assertTrue((artifacts_dir / "meta.json").exists())
        index = json.loads((self.home / ".wicked-understanding" / "index.json").read_text())
        self.assertIn("repos", index)
        self.assertEqual(len(index["repos"]), 1)

    def test_remote_url_variants_yield_same_artifacts_dir(self):
        """https / git@ / trailing-slash variants all resolve to the SAME store key."""
        if not self.have_git:
            self.skipTest("git not available")

        printed_dirs = set()
        for url in URL_VARIANTS:
            self._init_repo_with_remote(url)
            result = _support.run_script(
                _support.INIT_SCRIPT, "path", "--repo-root", self.repo, env=self.env
            )
            self.assertEqual(result.returncode, 0, f"{url}: {result.stderr}")
            printed_dirs.add(result.stdout.strip())

        self.assertEqual(
            len(printed_dirs),
            1,
            f"remote variants produced differing artifacts dirs: {printed_dirs}",
        )
        only = next(iter(printed_dirs))
        self.assertTrue(only.endswith(EXPECTED_KEY) or only.endswith(EXPECTED_KEY.replace("/", "\\")),
                        f"artifacts dir does not end with {EXPECTED_KEY}: {only}")

    def test_list_runs_and_reports_repo(self):
        """`list` exits 0 and shows the repo after init."""
        init_res = _support.run_script(
            _support.INIT_SCRIPT, "init", "--repo-root", self.repo, env=self.env
        )
        self.assertEqual(init_res.returncode, 0, init_res.stderr)

        list_res = _support.run_script(_support.INIT_SCRIPT, "list", env=self.env)
        self.assertEqual(list_res.returncode, 0, list_res.stderr)
        # The repo dir name is the key (no remote), so it must appear in the listing.
        self.assertIn(self.repo.name, list_res.stdout)

    def test_list_on_empty_store_runs(self):
        """`list` against a fresh (empty) store still exits 0 with a hint."""
        list_res = _support.run_script(_support.INIT_SCRIPT, "list", env=self.env)
        self.assertEqual(list_res.returncode, 0, list_res.stderr)
        self.assertIn("No repos", list_res.stdout)


if __name__ == "__main__":
    unittest.main()
