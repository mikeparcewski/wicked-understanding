#!/usr/bin/env python3
"""
init_understanding.py — Initialize and manage the ~/.wicked-understanding/ store.

The understanding store is where all repo analysis artifacts live, structured
for progressive loading by agents. Generated skills are NOT stored here —
they go into the repo's .claude/skills/ and .agents/skills/ directories.

Usage:
    # Initialize store entry for a repo and return the artifacts directory
    python3 init_understanding.py init --repo-root /path/to/repo

    # List all repos in the store
    python3 init_understanding.py list

    # Show the artifacts directory for a repo (for use in scripts)
    python3 init_understanding.py path --repo-root /path/to/repo

Store layout:
    ~/.wicked-understanding/
    ├── index.json                          # all known repos
    └── repos/
        └── github.com/acme/payments/       # keyed by git remote (or repo name)
            ├── meta.json                   # path, git URL, timestamps
            ├── survey.md
            ├── survey.manifest.json
            ├── architecture.md
            ├── architecture.manifest.json
            ├── domain.md
            ├── domain.manifest.json
            ├── technical.md
            ├── technical.manifest.json
            ├── ops.md
            └── ops.manifest.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UNDERSTANDING_ROOT = Path.home() / ".wicked-understanding"


def normalize_remote_url(url: str) -> str:
    """Turn any git remote URL into a consistent path-safe key."""
    url = url.strip()
    # Strip protocol: https://, git://, ssh://
    url = re.sub(r'^(https?|git|ssh)://', '', url)
    # Strip a leading user@ (e.g. git@). Works for BOTH the scp short form
    # (git@host:path) and the ssh-URL form (ssh://git@host/path) — the old
    # colon-only match silently left "git@" on the ssh-URL form.
    url = re.sub(r'^[^@/]+@', '', url)
    # Drop a :port that precedes the path (host:22/path → host/path)
    url = re.sub(r'^([^/:]+):(\d+)(?=/|$)', r'\1', url)
    # scp separator: any remaining host:path colon → host/path
    url = re.sub(r'^([^/:]+):', r'\1/', url)
    # Strip .git suffix
    url = re.sub(r'\.git$', '', url)
    # Strip trailing slashes
    url = url.rstrip('/')
    # Replace characters that aren't safe in directory names
    url = re.sub(r'[^a-zA-Z0-9._/\-]', '_', url)
    return url


def get_repo_key(repo_root: Path) -> tuple[str, str | None]:
    """
    Derive a unique key for this repo. Returns (key, git_remote_url).
    Prefers git remote URL; falls back to repo directory name.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            remote_url = result.stdout.strip()
            key = normalize_remote_url(remote_url)
            return key, remote_url
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: use repo directory name
    return repo_root.name, None


def get_artifacts_dir(repo_root: Path) -> Path:
    """Return the artifacts directory for a repo, creating it if needed."""
    key, _ = get_repo_key(repo_root)
    artifacts_dir = UNDERSTANDING_ROOT / "repos" / key
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def load_index() -> dict:
    index_path = UNDERSTANDING_ROOT / "index.json"
    if index_path.exists():
        try:
            return json.loads(index_path.read_text())
        except json.JSONDecodeError:
            pass
    return {"repos": {}}


def save_index(index: dict):
    UNDERSTANDING_ROOT.mkdir(parents=True, exist_ok=True)
    index_path = UNDERSTANDING_ROOT / "index.json"
    index_path.write_text(json.dumps(index, indent=2))


def cmd_init(repo_root: Path) -> Path:
    """Initialize store entry for a repo. Returns artifacts directory path."""
    UNDERSTANDING_ROOT.mkdir(parents=True, exist_ok=True)
    (UNDERSTANDING_ROOT / "repos").mkdir(exist_ok=True)

    key, git_remote = get_repo_key(repo_root)
    artifacts_dir = UNDERSTANDING_ROOT / "repos" / key
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Write or update meta.json
    meta_path = artifacts_dir / "meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            pass

    now = datetime.now(timezone.utc).isoformat()
    meta.update({
        "key": key,
        "repo_root": str(repo_root.resolve()),
        "git_remote": git_remote,
        "last_accessed": now,
    })
    if "first_analyzed" not in meta:
        meta["first_analyzed"] = now

    meta_path.write_text(json.dumps(meta, indent=2))

    # Update index
    index = load_index()
    index["repos"][key] = {
        "repo_root": str(repo_root.resolve()),
        "git_remote": git_remote,
        "last_accessed": now,
        "artifacts_dir": str(artifacts_dir),
    }
    save_index(index)

    # Print the artifacts directory path (for use in shell scripts / subprocesses)
    print(str(artifacts_dir))
    return artifacts_dir


def cmd_path(repo_root: Path):
    """Print the artifacts directory path for a repo (creates if missing)."""
    artifacts_dir = get_artifacts_dir(repo_root)
    print(str(artifacts_dir))


def cmd_list():
    """List all repos in the understanding store."""
    index = load_index()
    repos = index.get("repos", {})

    if not repos:
        print("No repos in ~/.wicked-understanding/ yet.")
        print("Run: python3 init_understanding.py init --repo-root /path/to/repo")
        return

    print(f"{'Key':<45} {'Last accessed':<22} {'Root'}")
    print("-" * 100)
    for key, info in sorted(repos.items(), key=lambda x: x[1].get("last_accessed", ""), reverse=True):
        last = info.get("last_accessed", "?")[:19]
        root = info.get("repo_root", "?")
        print(f"{key:<45} {last:<22} {root}")


def cmd_viewer(repo_root: Path, output: Path | None = None):
    """
    Generate (or regenerate) the HTML viewer for a repo from the understanding store.
    The viewer is written to {artifacts_dir}/viewer.html by default.
    """
    artifacts_dir = get_artifacts_dir(repo_root)

    if output is None:
        output = artifacts_dir / "viewer.html"

    # Find generate_viewer.py relative to this script
    script_dir = Path(__file__).parent
    viewer_script = script_dir / ".." / ".." / "repo-wiki-planner" / "scripts" / "generate_viewer.py"
    viewer_script = viewer_script.resolve()

    if not viewer_script.exists():
        print(f"Error: generate_viewer.py not found at {viewer_script}", file=sys.stderr)
        sys.exit(1)

    # Build a temporary skill-like directory from the understanding store
    # generate_viewer.py reads refs/*.md files
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        refs_dir = tmp_path / "refs"
        refs_dir.mkdir()

        # Copy all .md files (that are wiki article refs) into tmp refs/
        for md_file in artifacts_dir.glob("*.md"):
            shutil.copy(md_file, refs_dir / md_file.name)

        # Also check for a wiki/refs/ structure if skills have been generated
        repo_key, _ = get_repo_key(repo_root)
        for skill_dir in [".claude/skills/wiki", ".agents/skills/wiki"]:
            wiki_refs = repo_root / skill_dir / "refs"
            if wiki_refs.exists():
                for md_file in wiki_refs.glob("*.md"):
                    shutil.copy(md_file, refs_dir / md_file.name)
                break

        # Write a minimal SKILL.md for the viewer
        (tmp_path / "SKILL.md").write_text(
            f"---\nname: {repo_root.name}-wiki\n---\n# {repo_root.name} Wiki\n"
        )

        result = subprocess.run(
            [sys.executable, str(viewer_script),
             "--skill-dir", str(tmp_path),
             "--output", str(output)],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"Error generating viewer: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        print(result.stdout.strip())
        print(f"Open: {output}")


def main():
    parser = argparse.ArgumentParser(description="Manage ~/.wicked-understanding/ analysis store")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize store entry for a repo; prints artifacts dir")
    p_init.add_argument("--repo-root", required=True, type=Path)

    p_path = sub.add_parser("path", help="Print artifacts directory for a repo")
    p_path.add_argument("--repo-root", required=True, type=Path)

    sub.add_parser("list", help="List all repos in the store")

    p_view = sub.add_parser("viewer", help="Generate HTML viewer from latest store data")
    p_view.add_argument("--repo-root", required=True, type=Path)
    p_view.add_argument("--output", type=Path, default=None)

    args = parser.parse_args()

    if args.cmd == "init":
        cmd_init(args.repo_root.resolve())
    elif args.cmd == "path":
        cmd_path(args.repo_root.resolve())
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "viewer":
        cmd_viewer(args.repo_root.resolve(), args.output)


if __name__ == "__main__":
    main()
