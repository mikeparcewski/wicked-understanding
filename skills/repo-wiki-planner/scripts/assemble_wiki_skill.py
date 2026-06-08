#!/usr/bin/env python3
"""
assemble_wiki_skill.py — Build {repo}-wiki/SKILL.md from the wiki plan
and analysis artifacts.

Usage:
    python3 assemble_wiki_skill.py \
        --plan-file {repo}-wiki-plan.json \
        --skill-staging {repo}-wiki \
        --artifacts-dir /path/to/artifacts

Reads the plan and analysis artifacts, then writes a SKILL.md optimized
for agent use into the skill staging directory. The SKILL.md is the
always-in-context router + quick reference. Refs are loaded on demand.

Target size: 80-150 lines.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# --- YAML-like frontmatter parser (no external deps) ---

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown. Returns (meta, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:].strip()
    meta = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta, body


def extract_section(text: str, heading: str) -> str:
    """Extract content of a ## heading section from markdown."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(pattern, line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return ""
    # Collect until next ## heading
    result = []
    for line in lines[start:]:
        if re.match(r"^##\s+", line) and result:
            break
        result.append(line)
    return "\n".join(result).strip()


def extract_table_rows(section_text: str, max_rows: int = 7) -> list[list[str]]:
    """Extract the data rows of a markdown table — skips the header and the
    `---|---` separator. Only rows after the separator are returned."""
    rows = []
    in_table = False
    for line in section_text.splitlines():
        if "|" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                in_table = True  # separator line — data rows follow
                continue
            if in_table:
                rows.append(cells)
    return rows[:max_rows]


def extract_entities(section_text: str, max_items: int = 7) -> list[list[str]]:
    """Extract (name, one-line description) pairs from a "Core Entities" section.
    The domain lens emits entities as `### Name` H3 blocks with a
    `- **Represents**: ...` bullet, so parse those. Falls back to table rows if
    the section happens to be a markdown table instead."""
    entities: list[list[str]] = []
    name = None
    desc = ""
    for line in section_text.splitlines():
        h3 = re.match(r"^###\s+(.+?)\s*$", line)
        if h3:
            if name:
                entities.append([name, desc])
            name = h3.group(1).strip().strip("`")
            desc = ""
            continue
        if name and not desc:
            m = re.match(r"^\s*[-*]\s*\*\*Represents\*\*\s*:\s*(.+)$", line, re.IGNORECASE)
            if m:
                desc = m.group(1).strip()
    if name:
        entities.append([name, desc])
    if entities:
        return entities[:max_items]
    return extract_table_rows(section_text, max_rows=max_items)


def load_artifact(artifacts_dir: Path, filename: str) -> str:
    """Load an analysis artifact file, return empty string if missing."""
    path = artifacts_dir / filename
    if path.exists():
        return path.read_text()
    return ""


def main():
    parser = argparse.ArgumentParser(description="Assemble wiki SKILL.md from plan + artifacts")
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--skill-staging", required=True, help="Directory to write {repo}-wiki/SKILL.md into")
    parser.add_argument("--artifacts-dir", required=True)
    args = parser.parse_args()

    plan_path = Path(args.plan_file)
    staging_dir = Path(args.skill_staging)
    artifacts_dir = Path(args.artifacts_dir)

    if not plan_path.exists():
        print(f"Error: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    with open(plan_path) as f:
        plan = json.load(f)

    repo = plan["repo"]
    # Kebab-case the repo name into an agentskills-valid, collision-safe slug:
    # lowercase, every run of non-[a-z0-9-] chars → a single hyphen, trimmed.
    # The wiki skill installs as a sibling folder named {repo_slug}-wiki and its
    # frontmatter `name` MUST equal that folder (agentskills rule).
    repo_slug = re.sub(r'[^a-z0-9-]+', '-', repo.lower()).strip('-')
    stack = plan.get("stack", "unknown stack")
    repo_type = plan.get("type", "service")
    articles = plan.get("articles", [])
    generated_at = plan.get("generated_at", "")

    # Load analysis artifacts (bare names — the store dir is already per-repo)
    survey = load_artifact(artifacts_dir, "survey.md")
    domain = load_artifact(artifacts_dir, "domain.md")
    ops = load_artifact(artifacts_dir, "ops.md")

    # --- Extract content for quick reference ---

    # Dev commands (from ops.md "Daily Development Commands" table)
    commands_text = extract_section(ops, "Daily Development Commands")
    command_rows = extract_table_rows(commands_text, max_rows=6)
    commands_md = ""
    for row in command_rows:
        if len(row) >= 2:
            commands_md += f"  {row[0]:<20}  # {row[1]}\n"

    # Key entities (from domain.md "Core Entities" — H3 blocks, table fallback)
    entities_text = extract_section(domain, "Core Entities")
    entity_rows = extract_entities(entities_text, max_items=7)

    # Key files (from survey.md "Key Files" table — top 7)
    files_text = extract_section(survey, "Key Files")
    file_rows = extract_table_rows(files_text, max_rows=7)
    files_md = ""
    for row in file_rows:
        if len(row) >= 2:
            files_md += f"  {row[0]:<35} {row[1][:60]}\n"

    # Build purpose summary (from survey.md "Purpose & Context")
    purpose_text = extract_section(survey, "Purpose & Context")
    purpose_one_line = " ".join(purpose_text.split())[:140] if purpose_text else f"{repo} — {repo_type}"

    # Build the load guide from the article list. The plan's `ref_file` is the
    # SINGLE source of truth for the on-disk filename — we never hardcode a name
    # here (that was the bug that produced dead links). The question label is the
    # only thing keyed off the article type.
    TYPE_QUESTION = {
        "product-overview":      "Understand what this system is / does",
        "architecture-overview": "Understand the architecture / component map",
        "api-reference":         "Call or understand the API surface",
        "onboarding-maintainer": "Set up a dev environment from scratch",
        "design-pattern":        "Understand recurring code patterns",
        "agent-roster":          "Know what agents / skills are defined",
        "runbook":               "Run operations or debug failures",
    }
    load_rows = []
    for art in sorted(articles, key=lambda a: a.get("priority", 99)):
        atype = art["type"]
        ref_file = art.get("ref_file", "").strip()
        if not ref_file:
            continue  # no stable filename → can't produce a working link
        ref_path = ref_file if ref_file.startswith("refs/") else f"refs/{ref_file}"
        subject = art.get("subject", "") or art.get("title", atype)
        if atype == "capability":
            question = f"How {subject} works end-to-end"
        elif atype == "concept-explanation":
            question = f'What "{subject}" means'
        else:
            question = TYPE_QUESTION.get(atype, art.get("title", atype))
        load_rows.append(f"| {question} | `{ref_path}` |")

    load_guide_md = "\n".join(load_rows)

    # Articles table
    articles_table = ""
    audience_labels = {"both": "both", "maintainer": "maintainer", "user": "user"}
    for art in sorted(articles, key=lambda a: a.get("priority", 99)):
        title = art.get("title", art["type"])
        aud = audience_labels.get(art.get("audience", "maintainer"), "maintainer")
        # Confidence not yet known at assembly time — mark as TBD
        articles_table += f"| {title:<40} | {aud:<12} | (see article) |\n"

    # Build description
    # Extract top 3 entity names for description
    entity_names = [r[0].strip("`") for r in entity_rows[:3]] if entity_rows else []
    entity_str = ", ".join(entity_names) if entity_names else "core entities"

    n_caps = sum(1 for a in articles if a["type"] == "capability")
    n_ops = sum(1 for a in articles if a["type"] == "runbook")

    # Build the "Contains:" fragment list from the plan's STRUCTURED article set
    # (not by parsing free-form architecture prose — that proved brittle). Joined
    # with "; " for no dangling commas and correct singular/plural.
    contains = []
    if any(a["type"] == "architecture-overview" for a in articles):
        contains.append("an architecture overview")
    contains.append(f"domain model ({entity_str})")
    if any(a["type"] == "api-reference" for a in articles):
        contains.append("an API reference")
    if any(a["type"] == "onboarding-maintainer" for a in articles):
        contains.append("maintainer onboarding")
    if n_caps > 0:
        cap_names = [a.get("subject", "") for a in articles if a["type"] == "capability"][:3]
        frag = f"{n_caps} capability deep-dive{'s' if n_caps != 1 else ''}"
        named = ", ".join(filter(None, cap_names))
        contains.append(f"{frag} ({named})" if named else frag)
    if n_ops > 0:
        contains.append(f"{n_ops} operational runbook{'s' if n_ops != 1 else ''}")

    description = (
        f"Living wiki for {repo} — a {repo_type} built with {stack}. "
        f"Contains: {'; '.join(contains)}. "
        f"Load for any question about {repo}: architecture decisions, domain rules, "
        "API conventions, or how to add new features. "
        "Prefer this over raw code navigation — it synthesizes intent and patterns "
        "spread across dozens of files."
    )

    # --- Assemble SKILL.md ---
    # Name is per-repo ({repo}-wiki) so wikis for different repos don't collide
    # and the viewer's get_repo_name() (which strips "-wiki") resolves correctly.
    skill_content = f"""---
name: {repo_slug}-wiki
description: >
  {description}
generated: {generated_at[:10] if generated_at else ""}
---

# {repo} Wiki

> {purpose_one_line}

---

## Load guide

Load a ref only when you need it — they are detailed.

| I need to... | Read |
|---|---|
{load_guide_md}

---

## Quick reference (always in context)

**Stack**: {stack} | **Type**: {repo_type}

### Dev commands
```bash
{commands_md.rstrip() or "  # see refs/onboard.md for setup commands"}
```

### Key entities
| Entity | What it represents |
|---|---|
{chr(10).join(f"| `{r[0].strip('`')}` | {r[1][:70] if len(r) > 1 else ''} |" for r in entity_rows) if entity_rows else "| (see refs/overview.md) | |"}

### Key file locations
```
{files_md.rstrip() or "# see refs/onboard.md for file map"}
```

---

## Articles in this wiki

| Title | Audience | Confidence |
|---|---|---|
{articles_table.rstrip()}
"""

    # Write to skill staging directory
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "refs").mkdir(exist_ok=True)
    skill_path = staging_dir / "SKILL.md"
    skill_path.write_text(skill_content)

    lines = len(skill_content.splitlines())
    print(f"Wrote {skill_path} ({lines} lines)")
    if lines > 150:
        print(f"WARNING: SKILL.md is {lines} lines — target is under 150. Consider trimming entities or file locations.", file=sys.stderr)


if __name__ == "__main__":
    main()
