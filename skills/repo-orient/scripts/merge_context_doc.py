#!/usr/bin/env python3
"""
merge_context_doc.py — Idempotently merge a wicked-understanding "context block"
into an agent context file (CLAUDE.md / AGENTS.md / GEMINI.md) WITHOUT clobbering
anything the human wrote.

The block is delimited by HTML-comment markers. On every run:
  - file missing            → create it containing only the block
  - file exists, no markers → append the block (preceding content untouched)
  - file exists, has markers→ replace ONLY the text between the markers

Everything outside the markers is preserved byte-for-byte, so a hand-authored
CLAUDE.md keeps its rules and only the managed section is refreshed.

Usage:
    python3 merge_context_doc.py --target /path/to/CLAUDE.md --content-file /tmp/block.md
    # optional: --marker wicked-understanding   (default)
    # optional: --verify-routes /path/to/generated/skills  (dead-link guard)

Cross-platform: Python 3 stdlib only (pathlib, re).
"""

import argparse
import re
import sys
from pathlib import Path

# A routed skill token: lowercase, digits, hyphens only (e.g. `acme-fix-bug`).
SKILL_TOKEN_RE = re.compile(r"`([a-z0-9-]+)`")
# A wiki ref the routing table points at (e.g. `refs/arch.md`); the leading
# backtick is optional because the body may write it bare or fenced.
REF_TOKEN_RE = re.compile(r"refs/([A-Za-z0-9._-]+\.md)")
# Suffix under which generated wiki packages live (e.g. `acme-wiki/`).
WIKI_DIR_SUFFIX = "-wiki"

START_TMPL = "<!-- {marker}:context:start -->"
END_TMPL = "<!-- {marker}:context:end -->"
AUTOGEN_NOTE = (
    "<!-- Managed by wicked-understanding (repo-orient). Edits inside this block "
    "are overwritten on refresh; write your own rules OUTSIDE it. -->"
)


def build_block(marker: str, content: str) -> str:
    """Wrap content in the managed markers + an autogen note."""
    start = START_TMPL.format(marker=marker)
    end = END_TMPL.format(marker=marker)
    body = content.strip("\n")
    return f"{start}\n{AUTOGEN_NOTE}\n{body}\n{end}"


def merge(existing: str, marker: str, content: str) -> tuple[str, str]:
    """Return (new_text, action). action ∈ {created, replaced, appended}."""
    block = build_block(marker, content)
    start = re.escape(START_TMPL.format(marker=marker))
    end = re.escape(END_TMPL.format(marker=marker))
    # DOTALL: match across the whole block, non-greedy so nested-looking text is safe.
    pattern = re.compile(rf"{start}.*?{end}", re.DOTALL)

    if not existing.strip():
        return block + "\n", "created"

    if pattern.search(existing):
        # Replace only the managed block; everything else is untouched.
        new_text = pattern.sub(lambda _m: block, existing, count=1)
        return new_text, "replaced"

    # Append, separated by exactly one blank line, preserving prior content.
    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block + "\n", "appended"


def verify_routes(content: str, package_dir: Path) -> tuple[list[str], list[str], int, int]:
    """Scan `content` for routed tokens and check each resolves under `package_dir`.

    Returns (dead_skills, dead_refs, ok_skills, ok_refs). Empty dead lists ⇒ pass.

    Deterministic, conservative — flags only clear routes, never prose:

    Skill names
        Every backtick token matching ^[a-z0-9-]+$ that contains a hyphen is a
        *candidate* route (the generated task skills are all `{slug}-fix-bug`,
        `{slug}-add-feature`, …, `{slug}-wiki`). A candidate resolves if
        `<package-dir>/<token>/` is a directory. Unresolved candidates are
        reported as dead links ONLY IF at least one sibling candidate DID
        resolve — so a doc verified against a repo with no package dir (nothing
        resolves) is not nuked wholesale. The hyphen requirement keeps ordinary
        backticked words (`true`, `null`, `npm`) out of scope.

    Wiki refs
        Every `refs/<file>.md` mentioned must exist under some
        `<package-dir>/*-wiki/refs/<file>.md`. Refs are checked only when the
        package dir actually contains a `*-wiki/` package — mirroring the skill
        guard, so a missing wiki package doesn't mass-report every ref.
    """
    # ---- skills -----------------------------------------------------------
    skill_candidates = [t for t in dict.fromkeys(SKILL_TOKEN_RE.findall(content)) if "-" in t]
    resolved_skills = [t for t in skill_candidates if (package_dir / t).is_dir()]
    unresolved_skills = [t for t in skill_candidates if t not in resolved_skills]
    # Sibling guard: only trust the skill routes if at least one resolved.
    dead_skills = unresolved_skills if resolved_skills else []
    ok_skills = len(resolved_skills)

    # ---- wiki refs --------------------------------------------------------
    wiki_dirs = [p for p in sorted(package_dir.glob(f"*{WIKI_DIR_SUFFIX}")) if p.is_dir()]
    ref_tokens = list(dict.fromkeys(REF_TOKEN_RE.findall(content)))
    dead_refs: list[str] = []
    ok_refs = 0
    if wiki_dirs:  # no wiki package ⇒ nothing to verify against; skip (no false alarms).
        for ref in ref_tokens:
            if any((wd / "refs" / ref).is_file() for wd in wiki_dirs):
                ok_refs += 1
            else:
                dead_refs.append(ref)

    return dead_skills, dead_refs, ok_skills, ok_refs


def main():
    ap = argparse.ArgumentParser(description="Merge a managed context block into an agent doc")
    ap.add_argument("--target", required=True, type=Path, help="CLAUDE.md / AGENTS.md / GEMINI.md path")
    ap.add_argument("--content-file", required=True, type=Path, help="File holding the block body to insert")
    ap.add_argument("--marker", default="wicked-understanding", help="Marker id (default: wicked-understanding)")
    ap.add_argument(
        "--verify-routes",
        type=Path,
        metavar="PACKAGE_DIR",
        help="Before writing, confirm every routed skill/wiki-ref in the body "
        "resolves under PACKAGE_DIR (the generated skills/ dir). Exit non-zero "
        "WITHOUT writing if any dead links are found.",
    )
    args = ap.parse_args()

    if not args.content_file.exists():
        print(f"Error: content file not found: {args.content_file}", file=sys.stderr)
        sys.exit(1)

    content = args.content_file.read_text(encoding="utf-8")
    existing = args.target.read_text(encoding="utf-8") if args.target.exists() else ""

    new_text, action = merge(existing, args.marker, content)

    # Dead-link guard: verify BEFORE writing so the pipeline catches a stale
    # package (routes pointing at skills/refs that no longer exist).
    if args.verify_routes is not None:
        if not args.verify_routes.is_dir():
            print(f"Error: --verify-routes dir not found: {args.verify_routes}", file=sys.stderr)
            sys.exit(1)
        dead_skills, dead_refs, ok_skills, ok_refs = verify_routes(content, args.verify_routes)
        if dead_skills or dead_refs:
            print("verify-routes: dead links found (target NOT written):", file=sys.stderr)
            for tok in dead_skills:
                print(f"  dead skill route: `{tok}` (no {args.verify_routes / tok}/)", file=sys.stderr)
            for ref in dead_refs:
                print(f"  dead wiki ref: refs/{ref} (no *{WIKI_DIR_SUFFIX}/refs/{ref})", file=sys.stderr)
            sys.exit(1)
        print(f"verify-routes: {ok_skills} skill(s) + {ok_refs} ref(s) OK")

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(new_text, encoding="utf-8")
    print(f"{action}: {args.target} (managed block '{args.marker}:context', {len(content.splitlines())} body lines)")


if __name__ == "__main__":
    main()
