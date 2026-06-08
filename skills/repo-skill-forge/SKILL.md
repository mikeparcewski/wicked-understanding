---
name: repo-skill-forge
description: >
  Generate task-oriented workflow skills for a codebase into the per-repo store and install them via npx skills add. Produces fix-bug, add-feature, add-domain, write-tests, and scaffold skills — each tailored to this repo's specific patterns, file paths, and conventions. Skills progressively load deeper context from the wiki refs as the agent needs it. Trigger on: "build the skills", "generate the workflow skills", "make the dev skills", "forge the skills", or after repo-analyst completes analysis.
---

# repo-skill-forge

Generates four task-oriented workflow skills, each scoped to one common
agent path, plus a scaffolding skill. All read from the analysis artifacts
in `~/.wicked-understanding/`, write into the per-repo store under
`$ARTIFACTS_DIR/skills/`, then install via `npx skills add`.

---

## What gets generated

| Skill | Fires when agent is... | Always in context |
|---|---|---|
| `fix-bug` | Investigating or fixing a bug | Triage table, error chain, test commands, common sources |
| `add-feature` | Adding new functionality | Implementation steps, conventions, wiring guide |
| `add-domain` | Adding a new entity/domain/bounded context | Domain checklist, migration commands, entity template |
| `write-tests` | Writing or fixing tests | Framework patterns, fixture setup, what to test |
| `scaffold` | Starting a new component from scratch | File templates, naming conventions, DI registration |

Each skill carries a "Load for deeper context" table pointing into
`../{repo-slug}-wiki/refs/` so agents load only what the current step needs.

---

## Scale the set to the repo (don't always emit all five)

Read size and complexity from `survey.md` first, then generate only the skills
that earn their place. Emitting all five for a sub-~100-file repo is redundant —
`add-domain` and `scaffold` describe new-component ceremony a small flat repo
doesn't have, so they produce filler.

| Skill | Generate when |
|---|---|
| `fix-bug` | Always — dogfood-proven keeper |
| `add-feature` | Always — dogfood-proven keeper |
| `write-tests` | Repo has a test suite, or is medium+ (~100+ files) |
| `add-domain` | Larger / multi-module / multi-domain repo where adding a new entity or bounded context is a real recurring task |
| `scaffold` | Larger / multi-module repo where new-component scaffolding recurs |

If the survey is ambiguous on size, default to the always-two plus `write-tests`
when any tests exist. Note in your output which skills you skipped and why.

---

## Input

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

Load from `$ARTIFACTS_DIR`: `survey.md`, `architecture.md`, `domain.md`,
`technical.md`, `ops.md`. If artifacts are missing or stale, run
`repo-analyst` first.

Read `references/task-skill-templates.md` before writing any skill — it
defines the section structure, content sources, and quality bar for each.

---

## Output locations

```
$ARTIFACTS_DIR/skills/{repo-slug}-{skill-name}/SKILL.md
```

`{repo-slug}` = the repo name lowercased, with every run of non-`[a-z0-9-]`
chars replaced by a single hyphen, trimmed of leading/trailing hyphens (e.g.
`acme_app` → `acme-app`). Each skill's folder AND its frontmatter `name`
MUST equal `{repo-slug}-{skill-name}` — agentskills names are lowercase
letters/numbers/hyphens only and MUST equal the folder; a colon-namespaced name
won't install. Prefixing with the repo-slug also keeps skills from different
repos from colliding when installed into the same CLI.

One location — the per-repo store. The pipeline installs from here via
`npx skills add` (see "After generation"); nothing is written into the
analyzed repo's tree.

Generate the skills selected by the scaling rule above, dispatching subagents.

### When parallel subagents are available

Dispatch one subagent **per selected skill, all in a single batch**. The skills
are independent — each reads the same artifacts and writes its own file.
Give each subagent this brief:

```
Generate the `{skill-name}` task skill for the repository at {REPO_ROOT}.
Read the template section for `{skill-name}` in (bundled with this skill —
path relative to this skill's directory):
  references/task-skill-templates.md
Ground every path, command, and pattern in the analysis artifacts at:
  {ARTIFACTS_DIR}/{survey,architecture,domain,technical,ops}.md
Write the finished SKILL.md to (folder = frontmatter `name` = {repo-slug}-{skill-name},
where {repo-slug} is the repo name lowercased with non-[a-z0-9-] runs → a single
hyphen, trimmed):
  {ARTIFACTS_DIR}/skills/{repo-slug}-{skill-name}/SKILL.md
Obey every quality check in the template's section. Under 150 lines. Zero
placeholders — if an artifact section is thin, note the gap and lower confidence.
```

Skills to dispatch: the subset chosen by the scaling rule (always `fix-bug` +
`add-feature`; `write-tests`, `add-domain`, `scaffold` per repo size).

### Sequential fallback (single-threaded host)

Generate the selected subset in order `fix-bug` → `add-feature` → `add-domain` → `write-tests`
→ `scaffold`, following the same brief for each.

---

## Generation process for each skill

For each skill type, read the relevant section in `references/task-skill-templates.md`.
It specifies:
- Which analysis artifact sections feed which template sections
- What the always-in-context content must cover
- The "Load for deeper context" table rows to include
- Specific quality checks

**Key principle**: every file path, command, and pattern cited must trace
to a real value found in the analysis artifacts. No placeholders, no guesses.
If an artifact section is thin, note the gap and set confidence accordingly.

---

## Quality bar

For every generated skill:

- [ ] Description names the repo, the task, and 2-3 specific things it covers
- [ ] Always-in-context section fits under 120 lines
- [ ] Every file path is real (from survey.md or architecture.md)
- [ ] Every command is runnable (from ops.md)
- [ ] "Load for deeper context" table has ≥ 3 rows pointing to wiki refs
- [ ] No section says "see the code" — it says which file and what to look for

---

## Validate the package installs

Before installing, prove the real tool accepts every skill you generated. A
skill whose frontmatter `npx skills` can't parse is **silently dropped** (exit
0, never installed) — most often a plain-scalar `description:` containing `: `
("Nested mappings are not allowed in compact mappings"; the templates fix this
with `description: >`). So this count check is **mandatory** before
`npx skills add … --all`:

```bash
npx -y skills add "$ARTIFACTS_DIR/skills" --list
```

Confirm the "Found N skill(s)" it reports EQUALS the number of skill folders you
generated under `$ARTIFACTS_DIR/skills/` (count them:
`ls -d "$ARTIFACTS_DIR"/skills/*/ | wc -l`). If N is fewer, the package has
invalid frontmatter — **FAIL loudly, name which folder(s) were dropped** (the
ones absent from the `--list` output), fix that frontmatter (make `description:`
a folded block scalar `>`), and re-run the check. Do **not** install a partial
package.

## Install the generated skills

After the subset is written and the count check passes, install it into the
user's agent CLI(s). The pipeline runs this itself — the user is **not** asked
to run it:

```bash
npx skills add "$ARTIFACTS_DIR/skills" --all
```

This is cross-CLI: it installs the generated skills wherever the user's agent
CLI looks for them. The folders install under their generated names
(`{repo-slug}-fix-bug`, `{repo-slug}-add-feature`, …); each skill's
`../{repo-slug}-wiki/refs/...` links keep resolving because `{repo-slug}-fix-bug/`
and `{repo-slug}-wiki/` are siblings under `$ARTIFACTS_DIR/skills/`.

## After generation

```
Task skills written to (the subset chosen for this repo's size) and installed
via `npx skills add "$ARTIFACTS_DIR/skills" --all`:

  $ARTIFACTS_DIR/skills/
    ├── {repo-slug}-fix-bug/SKILL.md
    ├── {repo-slug}-add-feature/SKILL.md
    └── {repo-slug}-{write-tests, add-domain, scaffold — only those generated}/SKILL.md

State which skills were skipped and why (e.g. "skipped add-domain + scaffold:
sub-100-file flat repo, no recurring new-component need").
Skills are installed and active immediately.
Run "generate the wiki" to build the wiki refs these skills load from.
```
