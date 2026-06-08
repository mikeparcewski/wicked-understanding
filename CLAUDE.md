# wicked-understanding

Portable Agent Skills (installed via `npx skills`): **9 skills that analyze any
repository** and emit three outputs — **task workflow skills** (`fix-bug`,
`add-feature`, `add-domain`, `write-tests`, `scaffold`), a **wiki** (agent-loadable
skill + standalone HTML viewer), and a **merge-safe context doc** (`CLAUDE.md` /
`AGENTS.md`) that routes agents to them. Analysis is cached in
`~/.wicked-understanding/repos/{repo-key}/` and refreshed incrementally.

This file is the operating contract for working **on the plugin**. For the
design, read `README.md` — don't restate it here. (`AGENTS.md` is a symlink to
this file, so tools that read AGENTS.md get the identical rules with zero drift.)

## The inventory (real — no filler)

| Piece | What it is | Output |
|---|---|---|
| `repo-surveyor` | mandatory first pass | `survey.md` |
| `repo-architect` · `-domain-analyst` · `-tech-analyst` · `-ops-analyst` | the 4 lenses | `architecture/domain/technical/ops.md` |
| `repo-analyst` | orchestrator: freshness → dispatch lenses → forge/wiki | refreshed artifacts |
| `repo-skill-forge` | generates the task skills (scaled to repo size) | `$ARTIFACTS_DIR/skills/*` → `npx skills add` |
| `repo-wiki-planner` | generates the wiki skill + viewer | `$ARTIFACTS_DIR/skills/wiki/` → `npx skills add` |
| `repo-orient` | writes the always-in-context context doc, routing to the generated skills | merge-safe `CLAUDE.md` / `AGENTS.md` |

Six deterministic scripts do the only non-LLM work (see *Don't rebuild*).
Everything else is an LLM dispatched as a subagent.

---

## Voice

Factual, brutally honest, product-focused. Not nice. Not agreeable.

**Do not:** agree to appease · soften bad news · hedge when evidence exists ·
open with "Great question" / "You're absolutely right" · say "we" for your
mistakes · pad with restatement · invent structure to look thorough.

**Do:** lead with what changes the next action · disagree with evidence ·
surface every finding · separate true from not-yet-true · give exact counts ·
say "I don't know."

**Mandate:** the bar this plugin must clear — set by dogfooding it on 4 real
repos — is *a stranger can run it unattended and trust the output*. Today it
clears "runs and produces verifiably-accurate analysis"; it does **not** yet
clear "unattended" (templates need a careful operator to avoid filler). Closing
that gap is the work. Ship that, not a feature list. Niceness is friction.

---

## Architecture — locked decisions (do not relitigate)

- **Agents do LLM work; scripts do deterministic mechanics.** Lens analysis,
  skill generation, and wiki-article generation are subagents. Store keying,
  freshness, router assembly, and the HTML viewer are Python. Never add a script
  that calls an LLM; never push deterministic plumbing into a prompt.
- **No `claude -p` subprocess orchestration.** Fan-out is native subagent
  dispatch (parallel where supported, sequential fallback). This keeps the
  pipeline host-agnostic and free of a CLI-on-PATH dependency. The three
  subprocess scripts were deleted on purpose — do not bring them back.
- **Bare artifact names** (`survey.md`, not `{repo}-survey.md`). The store dir
  is already per-repo; a prefix is redundant.
- **`slug` ≠ `ref_file`.** `slug` is the wiki-system identity (frontmatter +
  canonical IDs). `ref_file` is the on-disk filename a consumer loads. **`ref_file`
  is the single source of truth for links** — never hardcode a ref filename in a
  consumer (forge template or assembler). Hardcoding shipped dead links in every
  dogfood repo until it was fixed.
- **Distribution is `npx skills`, not a Claude plugin.** These are portable
  Agent Skills — no `.claude-plugin/manifest.json`. Every skill's frontmatter
  `name` MUST equal its folder (agentskills rule): `repo-surveyor`, not
  `wicked-understanding:surveyor`.
- **Scripts are bundled with their skill** under `scripts/` and invoked relative
  to the installed skill (no `$CLAUDE_PLUGIN_ROOT`). The orchestrator passes
  `ARTIFACTS_DIR` so forge/wiki don't hard-depend on a sibling's path; standalone
  they reach repo-analyst's keyer via `../repo-analyst/scripts/`.
- **Store is out-of-tree; generated skills install via `npx skills`.**
  `~/.wicked-understanding/repos/{key}/` holds the analysis AND the generated
  skill package under `skills/`; the pipeline runs `npx skills add` to install it
  into the user's CLI(s). Nothing generated is written into the analyzed repo's
  tree, and nothing generated belongs in THIS repo.
- **Lenses are the analysis source of truth; brain is an opt-in enricher — NOT
  an equal source.** The lenses always run and produce the artifacts: they read
  HEAD, so they're accurate and current. wicked-brain is an opt-in build-time
  enricher (`--enrich-from-brain`, default off) that *adds* supplementary design
  rationale (ADRs, decisions) the lenses can't see, in a separate marked section
  — it never replaces a lens artifact or overrides a lens fact (lens wins on
  conflict; brain may lag HEAD). Brain is NEVER a runtime dependency; output is
  self-contained and cross-CLI. **Proven by A/B on a Node repo: brain as a
  substitute source was worse** — it indexed a deleted `docs/`/ADR tree (stale),
  carried duplicate + cross-repo chunks, and missed the two highest-value gotchas
  the lenses caught. Do not promote brain to an equal/replacement source.

---

## Working style

**§1 — Map the contract before editing.** The 9 skills share contracts: artifact
filenames, the wiki plan JSON, `ref_file` naming, and the *exact section/format*
the assembler parses out of a lens's output. A change in a producer that a
consumer doesn't agree with is a latent dead-link / empty-table bug — the exact
class that shipped (assembler expected a table; the domain lens emits `### H3`
blocks → entities silently empty). Trace producer→consumer first.

**§2 — Estimates are wall-clock.** Dispatch subagents per file-disjoint chunk.
Four lens analyses, five skill generations, N article generations — independent,
so fan them out. Serialize only real dependencies (survey feeds the lenses).

**§3 — Dogfood IS the test suite.** There are no unit tests. "It works" means:
*ran the pipeline on a real repo of the relevant stack and read the output.*
**Cross-stack or it's not verified** — the templates lean TS/REST and silently
degrade on Go/Rust/functional/no-DB code. A Python pass proves nothing about the
Rust path. Generated skills go to a sandbox (`$ART/_generated/`), never into the
target repo's working tree, during evaluation.

**§4 — Verify, don't claim.** Every "done" carries an evidence path, a falsifier,
and the dependent not-yet-done.

| ❌ Wrong | ✅ Right |
|---|---|
| "Fixed the wiki assembler." | "Fixed 4 assembler bugs; verified 7/7 + 8/8 router links resolve on two real repos (a Python service + a Go repo) against the real ref files the dogfood wrote. Not yet done: the TS/REST template bias (4/4 repos needed operator override) and the forge→wiki `domain.md` gap." |
| "The pipeline works." | "Ran clean on 4 repos (Python/Node/86k-file-TS/Go); scripts exit 0; analysis spot-checked against source. Untested: stacks outside that set; unattended runs." |
| "Removed dead code." | "Deleted `run_parallel.py`/`run_wiki_parallel.py`/`generate_task_skills.py` + their SKILL.md refs; `py_compile` clean; grep shows no dangling references." |

**§5 — Parse structure, not prose.** The recurring defect here is a deterministic
script regex-scraping free-form LLM prose (the empty entity table; the mid-word
description). If a script needs a value from an artifact, take it from a
*structured* shape — a known heading, a table, an H3 block, or the plan JSON —
or don't compute it at all. Never best-effort-scrape generated paragraphs.

**§6 — Retire as you go.** Delete what you replace in the same change. The
agents-not-subprocess pivot deleted three scripts and their references in one
commit. If a change only adds, it's not a migration. What did this change delete?

**§7 — Cross-stack before "publishable."** A fix that makes the templates adapt
must be proven on a non-TS, non-OO repo (Go or Rust), not just re-run on Python.

---

## Universal don'ts

- **No name-swappable sentences.** The plugin's entire value is repo-*specific*
  output; a generated line that reads unchanged for any repo is filler and a bug.
  Holds for this file and for everything the pipeline emits.
- **No `claude -p` / subprocess orchestration.** LLM work = subagent dispatch.
- **No `{repo}-` artifact prefix.** The store dir is per-repo.
- **No hardcoded ref filenames** in any consumer. Use the plan's `ref_file`.
- **No new scripts for LLM work; no rebuilding the six scripts.**
- **No "it works" from a single-stack run.** §3.
- **No committed `.DS_Store`, no generated output checked into this repo.**

---

## Don't rebuild — the six scripts own all deterministic work

| Script | Owns |
|---|---|
| `repo-analyst/scripts/init_understanding.py` | store keying (git-remote → key), `index.json`, `meta.json`, artifacts-dir resolution |
| `repo-analyst/scripts/check_freshness.py` | git-diff (watch-pattern filtered) / mtime freshness per lens |
| `repo-analyst/scripts/detect_brain.py` | brain-reachability probe (picks brain vs. lenses for `--source auto`) |
| `repo-wiki-planner/scripts/assemble_wiki_skill.py` | wiki router `SKILL.md` from plan + artifacts (load-guide, quick-ref, description) |
| `repo-wiki-planner/scripts/generate_viewer.py` | self-contained HTML viewer from `refs/*.md` |
| `repo-orient/scripts/merge_context_doc.py` | merge a managed context block into CLAUDE.md/AGENTS.md without clobbering hand-written content |

Anything else — analysis, generation, judgment — is agent work, not a script.

---

## Commands

Two gates: the `tests/` suite (fast, deterministic) and a dogfood run (the real
proof — §3). No CI runner wired yet.

```bash
# unit gate — stdlib unittest (scripts + frontmatter validity + merge safety)
python3 -m unittest discover -s tests
python3 -m py_compile skills/repo-analyst/scripts/*.py skills/repo-wiki-planner/scripts/*.py

# install into any agent CLI (also how the pipeline installs generated skills)
npx skills add <owner>/wicked-understanding --all

# local dev — skills are discoverable here via the checked-in symlink
ls -l .claude/skills            # → ../skills

# inspect the analysis store
python3 skills/repo-analyst/scripts/init_understanding.py list
python3 skills/repo-analyst/scripts/check_freshness.py --repo-root <repo> --artifacts-dir <art>

# dogfood (the real test): per repo, dispatch a subagent that runs the full
# pipeline (survey → 4 lenses → forge → wiki) reading the skills, writing
# analysis to the store and generated skills to $ART/_generated/ (eval sandbox).
```

Store: `~/.wicked-understanding/repos/{repo-key}/` where `{repo-key}` is the
normalized git remote (e.g. `github.com/org/name`) or the dir name.

---

## Repo structure

```
.claude/skills -> ../skills      # symlink so skills load for local dev
skills/
  repo-surveyor/SKILL.md
  repo-architect/        SKILL.md + references/architecture-guide.md
  repo-domain-analyst/   SKILL.md + references/domain-guide.md
  repo-tech-analyst/     SKILL.md + references/technical-guide.md
  repo-ops-analyst/      SKILL.md + references/ops-guide.md
  repo-analyst/          SKILL.md + scripts/{init_understanding,check_freshness,detect_brain}.py
  repo-skill-forge/      SKILL.md + references/task-skill-templates.md
  repo-wiki-planner/     SKILL.md + references/{article-types,wiki-contract,wiki-skill-template}.md
                                  + scripts/{assemble_wiki_skill,generate_viewer}.py
  repo-orient/           SKILL.md + scripts/merge_context_doc.py
tests/                   stdlib-unittest suite (scripts + frontmatter + merge guards)
README.md  CLAUDE.md  AGENTS.md -> CLAUDE.md   # AGENTS.md mirrors CLAUDE.md
```

---

## Known gaps / open decisions (the repo's own "still not done")

Honest state as of 2026-06, after dogfooding on 4 repos (Python, Node, an
86k-file TS monorepo, Go). Evidence is in git history — don't claim more
resolved than this.

**Resolved (with evidence, not assertion):**
- ~~Template TS/REST/DI bias~~ — FIXED. The de-biased templates + lens guides
  produced clean Go output on a Go repo *following the templates literally,
  with no operator override* (the exact prior failure mode). Proven by re-dogfood.
- ~~forge→wiki `domain.md` gap~~ — FIXED via the `domain-reference` article type;
  8/8 router links resolved on the Go re-dogfood.
- ~~Overkill tax~~ — FIXED; forge scales the set to repo size (proven: selected
  all 5 for the 91-package Go repo; skips `add-domain`/`scaffold` on small flat repos).
- ~~No tests~~ — `tests/` suite added (27 green), incl. an assembler regression
  guard that locks in the dead-link / empty-entity / name fixes.

**Open:**
1. **No CI.** The suite exists; nothing runs it on push yet.
2. **The wiki ">8 articles → confirm with user" gate can't work in an autonomous /
   batch run** — the agent has to judge the trim itself. Make the cap deterministic
   or detect non-interactive mode.
3. **The brain path was A/B-tested against a live brain — and demoted to opt-in
   enricher.** Brain as a *substitute* analysis source was measurably worse on
   a Node repo (stale index of a deleted docs/ADR tree, duplicate +
   cross-repo chunks, missed the two highest-value gotchas the lenses caught).
   Design now: lenses always run (source of truth); brain only *adds* rationale on
   opt-in `--enrich-from-brain`. The enrichment-append flow still wants a full
   live-brain dogfood; the lens floor is proven.
4. **Strategic overlap with wicked-brain — RESOLVED.** Brain is an opt-in
   build-time *enricher* (supplementary rationale the lenses can't see), not a
   competitor and not an equal source. The lens floor is the source of truth.

---

## Constraints

- **Cross-platform.** Scripts run on macOS/Linux/Windows: `pathlib`, no shell-isms,
  Python 3 **stdlib only** (no third-party deps).
- **Dev tools** (`wicked-brain`, `wicked-garden`) are optional and not part of this
  plugin. The brain server is often down — never block on it.
