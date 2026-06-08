---
name: repo-wiki-planner
description: >
  Generate a wiki skill (agent-loadable) from repo-intelligence analysis artifacts into the per-repo store at $ARTIFACTS_DIR/skills/{repo-slug}-wiki/ and install it via npx skills add. Also generates viewer.html on demand from ~/.wicked-understanding/ data. Trigger on: "generate wiki", "build wiki", "document this repo", "create the wiki skill", "build docs", "show me the wiki", "open the viewer". Requires analysis artifacts from repo-analyst.
---

# repo-wiki-planner

**`{repo-slug}`** = the repo name lowercased, with every run of non-`[a-z0-9-]`
chars replaced by a single hyphen, trimmed of leading/trailing hyphens (e.g.
`acme_app` → `acme-app`). The wiki installs as a folder named `{repo-slug}-wiki`,
and its frontmatter `name` MUST equal that folder (agentskills rule). This is also
the sibling folder the forge's task skills load via `../{repo-slug}-wiki/refs/...`.
The assembler (`assemble_wiki_skill.py`) derives this slug itself for the
frontmatter; use the same `{repo-slug}` for the staging folder so they match.

Two modes:

| User intent | What happens |
|---|---|
| "generate wiki", "build the wiki" | Full wiki generation → `$ARTIFACTS_DIR/skills/{repo-slug}-wiki/`, installed via `npx skills add` |
| "show me the wiki", "open the viewer" | On-demand viewer only → reads from `~/.wicked-understanding/` |

---

## Mode 1: Generate wiki skill

### Input

Scripts ship in their skill's `scripts/` directory — invoke them by the path to
the installed skill (no `$CLAUDE_PLUGIN_ROOT`). Store keying is owned by
repo-analyst's `init_understanding.py`: use the `ARTIFACTS_DIR` that repo-analyst
passes when it orchestrates you; if run standalone, repo-analyst installs
alongside this skill — invoke
`python3 ../repo-analyst/scripts/init_understanding.py path --repo-root "$REPO_ROOT"`
(path relative to this skill's directory):

```bash
ARTIFACTS_DIR=$(python3 ../repo-analyst/scripts/init_understanding.py \
  path --repo-root "$REPO_ROOT")
```

Artifacts in `$ARTIFACTS_DIR` use bare names: `survey.md`, `architecture.md`,
`domain.md`, `technical.md`, `ops.md`.

### Output location

```
$ARTIFACTS_DIR/skills/{repo-slug}-wiki/        ← staged in the per-repo store
```

One location — a sibling of the forge's task-skill folders under
`$ARTIFACTS_DIR/skills/`, so the task skills' `../{repo-slug}-wiki/refs/...` links
resolve. The pipeline installs from here via `npx skills add` (see Step 4);
nothing is written into the analyzed repo's tree.

```bash
mkdir -p "$ARTIFACTS_DIR/skills/{repo-slug}-wiki/refs"
```

### Steps

**Step 1 — Read artifacts and write the plan**

Read all artifacts from `$ARTIFACTS_DIR`. Decide the article set (read
`references/article-types.md`):

Always: `product-overview`, `onboarding-maintainer`
Always if domain.md has ≥ 1 Core Entity: `domain-reference`
If ≥ 2 components: `architecture-overview`
If API found: `api-reference`
If ≥ 3 operations (cap 5): `capability` per feature
If ≥ 3 glossary terms (cap 5): `concept-explanation` per term
If multi-step ops (cap 3): `runbook`

Confirm the plan with the user if > 8 articles.

Write the plan to `/tmp/{repo}-wiki-plan.json`. Both downstream scripts read it:

```json
{
  "repo": "<repo-name>",
  "stack": "<primary stack>",
  "type": "<service|cli|library|...>",
  "generated_at": "<ISO datetime>",
  "articles": [
    {
      "type": "product-overview",
      "slug": "<repo>-overview",
      "ref_file": "overview.md",
      "title": "<Title Case>",
      "audience": "both",
      "priority": 1,
      "source_artifacts": ["survey.md", "domain.md"],
      "subject": ""
    }
  ]
}
```

`slug` is the article's wiki-system identity (frontmatter + canonical IDs).
`ref_file` is the stable on-disk filename the wiki SKILL.md and the generated
task skills load — assign it from this table:

| Article type | ref_file |
|---|---|
| product-overview | `overview.md` |
| architecture-overview | `arch.md` |
| api-reference | `api.md` |
| onboarding-maintainer | `onboard.md` |
| domain-reference | `domain.md` |
| capability | `cap-{feature-kebab}.md` |
| concept-explanation | `concept-{term-kebab}.md` |
| design-pattern | `patterns.md` (or `pattern-{name}.md` if > 1) |
| runbook | `ops.md` (or `runbook-{op}.md` if > 1) |
| agent-roster | `agents.md` |

**Step 2 — Generate article ref files (dispatch one agent per article)**

Articles are independent — dispatch one subagent per article, in a single
batch when parallel subagents are available; otherwise generate them yourself
in priority order. Give each subagent this brief:

```
Generate the `{type}` wiki article titled "{title}"{ for subject "{subject}"}.
Read the format contract FIRST (bundled with this skill — paths relative to
this skill's directory):
  references/wiki-contract.md
Then the content mapping for this type:
  references/article-types.md (§ {type})
Ground every section in these artifacts (the ONLY source — no memory/search):
  {for each source_artifact}: {ARTIFACTS_DIR}/{artifact}
Write the finished article (frontmatter + body + closer) to:
  $ARTIFACTS_DIR/skills/{repo-slug}-wiki/refs/{ref_file}
Pass all 5 lint self-checks (log to your output, not into the article).
Use only [src: file:{path}] citations.
```

**Step 3 — Assemble the wiki SKILL.md router**

Read `references/wiki-skill-template.md`, then run the deterministic assembler
(it extracts the quick-reference tables from artifacts and templates the router).
`assemble_wiki_skill.py` is bundled with this skill — invoke it relative to this
skill's directory:

```bash
python3 scripts/assemble_wiki_skill.py \
  --plan-file /tmp/{repo}-wiki-plan.json \
  --skill-staging "$ARTIFACTS_DIR/skills/{repo-slug}-wiki" \
  --artifacts-dir "$ARTIFACTS_DIR"
```

**Step 3.5 — Validate the package installs**

Before installing, prove the real tool accepts every skill in the package. A
skill whose frontmatter `npx skills` can't parse is **silently dropped** (exit
0, never installed) — most often a plain-scalar `description:` containing `: `
("Nested mappings are not allowed in compact mappings"). The assembler emits the
wiki's `description:` as a folded block scalar (`>`) for exactly this reason, but
the forge's sibling task skills must too — so check the whole package. This count
check is **mandatory** before `npx skills add … --all`:

```bash
npx -y skills add "$ARTIFACTS_DIR/skills" --list
```

Confirm the "Found N skill(s)" it reports EQUALS the number of skill folders
under `$ARTIFACTS_DIR/skills/` (count them:
`ls -d "$ARTIFACTS_DIR"/skills/*/ | wc -l`). If N is fewer, the package has
invalid frontmatter — **FAIL loudly, name which folder(s) were dropped** (the
ones absent from the `--list` output) and fix that frontmatter (make
`description:` a folded block scalar `>`) before installing. Do **not** install
a partial package.

**Step 4 — Install via npx skills add**

The assembled wiki skill is installed alongside the forge's task skills. The
orchestrator runs this once after forge + wiki both complete; when this skill
runs standalone, run it here (after the Step 3.5 count check passes). The user
is **not** asked to run it:

```bash
npx skills add "$ARTIFACTS_DIR/skills" --all
```

**Step 5 — Lint and confirm**

Lint self-check (from `references/wiki-contract.md`):
- No duplicate `canonical_for` IDs
- All `references` entries resolve
- Pages > 80 lines have ≥ 3 `references`
- Every `canonical_for` page has `## Purpose`

Tell the user:
```
Wiki skill written to $ARTIFACTS_DIR/skills/{repo-slug}-wiki/ and installed via
`npx skills add "$ARTIFACTS_DIR/skills" --all`.

{N} articles. Run "show me the wiki" to open the viewer.
```

---

## Mode 2: On-demand viewer

When the user says "show me the wiki", "open the viewer", or "view the docs":

`generate_viewer.py` is bundled with this skill — invoke it relative to this
skill's directory:

```bash
python3 scripts/generate_viewer.py \
  --skill-dir "$ARTIFACTS_DIR/skills/{repo-slug}-wiki" \
  --output "$ARTIFACTS_DIR/viewer.html"
```

Then open `$ARTIFACTS_DIR/viewer.html` for the user (present the file, or
print the path for them to open in a browser).

The viewer is always generated fresh from the latest refs — it is never
stored in the repo itself, only in `~/.wicked-understanding/`.

---

## Refresh mode

When analysis artifacts have been updated:
1. Re-run only articles whose source artifacts changed
2. Re-run `assemble_wiki_skill.py` to update the SKILL.md quick reference
3. Re-install with `npx skills add "$ARTIFACTS_DIR/skills" --all`
4. Regenerate viewer on next view request
