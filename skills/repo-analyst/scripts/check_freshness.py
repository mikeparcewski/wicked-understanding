#!/usr/bin/env python3
"""
check_freshness.py — Diff-aware freshness checker for repo-intelligence manifests.

Usage:
    python3 check_freshness.py --repo-root /path/to/repo --artifacts-dir /path/to/artifacts

Output: JSON to stdout
    {
      "survey":       {"status": "fresh|stale|missing", "reason": "..."},
      "architecture": {"status": "fresh|stale|missing", "reason": "..."},
      "domain":       {"status": "fresh|stale|missing", "reason": "..."},
      "technical":    {"status": "fresh|stale|missing", "reason": "..."},
      "ops":          {"status": "fresh|stale|missing", "reason": "..."}
    }
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


LENSES = ["survey", "architecture", "domain", "technical", "ops"]

# Artifacts use bare names (survey.md, architecture.md, …) because the store
# directory (~/.wicked-understanding/repos/{repo-key}/) is already per-repo.
LENS_TO_ARTIFACT = {
    "survey":       "survey",
    "architecture": "architecture",
    "domain":       "domain",
    "technical":    "technical",
    "ops":          "ops",
}


def load_manifest(artifacts_dir: Path, lens: str, repo_name: str) -> Optional[dict]:
    """Load the manifest JSON for a lens. Returns None if missing or invalid."""
    stem = LENS_TO_ARTIFACT[lens]
    manifest_path = artifacts_dir / f"{stem}.manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def git_available(repo_root: Path) -> bool:
    """Check if the repo is a git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def git_files_changed_since(repo_root: Path, since_commit: str, watch_patterns: list[str]) -> list[str]:
    """
    Return list of files changed since `since_commit` that match any watch pattern.
    Uses git log to find changes.
    """
    try:
        # Get all files changed since the commit
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", since_commit, "HEAD"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []

        changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        # Filter to only files matching watch patterns
        matching = []
        for filepath in changed_files:
            for pattern in watch_patterns:
                if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
                    os.path.basename(filepath), pattern.lstrip("**/")
                ):
                    matching.append(filepath)
                    break
        return matching

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def git_commit_exists(repo_root: Path, commit: str) -> bool:
    """Check if a commit hash exists in the repo history."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", commit],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def mtime_check(repo_root: Path, manifest: dict) -> tuple[str, str]:
    """
    Check freshness using file mtimes.
    Returns (status, reason).
    """
    files_analyzed = manifest.get("files_analyzed", [])
    watch_patterns = manifest.get("watch_patterns", [])

    for entry in files_analyzed:
        rel_path = entry["path"]
        stored_mtime = entry.get("mtime", 0)
        full_path = repo_root / rel_path

        if not full_path.exists():
            return "stale", f"{rel_path} was deleted"

        current_mtime = full_path.stat().st_mtime
        if abs(current_mtime - stored_mtime) > 1.0:  # 1-second tolerance
            return "stale", f"{rel_path} modified (mtime changed)"

    # Also check if new files matching watch patterns appeared
    for pattern in watch_patterns[:10]:  # Check first 10 patterns (performance)
        pattern_clean = pattern.lstrip("**/").lstrip("*/")
        if not pattern_clean or "*" in pattern_clean:
            continue
        # Check for exact files that might be new
        potential = repo_root / pattern_clean
        if potential.exists():
            rel = str(potential.relative_to(repo_root))
            known = {e["path"] for e in files_analyzed}
            if rel not in known:
                return "stale", f"new file found: {rel}"

    return "fresh", "all analyzed files unchanged (mtime)"


def check_lens(repo_root: Path, artifacts_dir: Path, repo_name: str, lens: str) -> dict:
    """Check freshness of a single lens. Returns {"status": ..., "reason": ...}."""
    manifest = load_manifest(artifacts_dir, lens, repo_name)

    if manifest is None:
        return {"status": "missing", "reason": "no manifest found"}

    # Check if the survey was regenerated after this lens ran (lens is now stale)
    if lens != "survey":
        survey_manifest = load_manifest(artifacts_dir, "survey", repo_name)
        if survey_manifest:
            lens_generated = manifest.get("generated_at", "")
            survey_generated = survey_manifest.get("generated_at", "")
            if survey_generated > lens_generated:
                return {
                    "status": "stale",
                    "reason": f"survey regenerated after this lens ran ({survey_generated} > {lens_generated})"
                }

    git_commit = manifest.get("git_commit")
    watch_patterns = manifest.get("watch_patterns", [])
    generated_at = manifest.get("generated_at", "unknown")

    # Prefer git-based check
    if git_commit and git_available(repo_root):
        if not git_commit_exists(repo_root, git_commit):
            return {
                "status": "stale",
                "reason": f"base commit {git_commit[:8]} not found in history (repo may have been reset)"
            }

        changed = git_files_changed_since(repo_root, git_commit, watch_patterns)
        if changed:
            preview = ", ".join(changed[:3])
            more = f" (+{len(changed)-3} more)" if len(changed) > 3 else ""
            return {
                "status": "stale",
                "reason": f"files changed since {git_commit[:8]}: {preview}{more}"
            }

        # Get current HEAD for display
        try:
            head = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            head = "unknown"

        return {
            "status": "fresh",
            "reason": f"no watched files changed since {git_commit[:8]} (HEAD: {head}, generated: {generated_at})"
        }

    # Fall back to mtime check
    status, reason = mtime_check(repo_root, manifest)
    return {"status": status, "reason": f"{reason} [mtime fallback — repo not git or no commit recorded]"}


def main():
    parser = argparse.ArgumentParser(description="Check freshness of repo-intelligence analysis artifacts")
    parser.add_argument("--repo-root", required=True, help="Absolute path to the repository root")
    parser.add_argument("--artifacts-dir", required=True, help="Directory containing manifest files")
    parser.add_argument("--repo-name", help="Override repo name (defaults to basename of repo-root)")
    parser.add_argument("--lenses", help="Comma-separated lenses to check (default: all)", default="all")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    repo_name = args.repo_name or repo_root.name

    if not repo_root.exists():
        print(json.dumps({"error": f"repo-root does not exist: {repo_root}"}))
        sys.exit(1)

    if not artifacts_dir.exists():
        # All missing if artifacts dir doesn't exist
        result = {lens: {"status": "missing", "reason": "artifacts directory does not exist"} for lens in LENSES}
        print(json.dumps(result, indent=2))
        return

    lenses_to_check = LENSES if args.lenses == "all" else [l.strip() for l in args.lenses.split(",")]

    results = {}
    for lens in lenses_to_check:
        if lens not in LENSES:
            results[lens] = {"status": "error", "reason": f"unknown lens: {lens}"}
            continue
        results[lens] = check_lens(repo_root, artifacts_dir, repo_name, lens)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
