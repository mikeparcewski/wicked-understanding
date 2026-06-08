---
name: repo-analyst
description: >
  Orchestrate all repo-intelligence lens skills with diff-awareness and parallel execution. Use when someone wants to analyze a repo (fully or partially), refresh outdated analysis, or run the full pipeline before forging a skill or building a wiki. Automatically detects which lenses are stale using manifest files and only re-runs what has changed. Runs all needed lenses in parallel when subagents are available. The lens subagents always produce the analysis by reading the repo at HEAD — that is the accurate, current source of truth. wicked-brain is an OPT-IN, additive build-time enricher (via `--enrich-from-brain`, default off): after the lens artifacts exist, it can append supplementary design rationale (ADRs, recorded decisions) the lenses cannot see; it never replaces a lens or overrides a lens fact. Trigger on: "analyze this repo", "refresh the analysis", "update the knowledge base for X", "run the pipeline on Y", "analyze and generate wiki", or whenever repo-skill-forge or repo-wiki-planner is about to run and artifacts may be stale.
---

# repo-analyst

Orchestrates `repo-surveyor` + up to 4 lens skills with diff-awareness and
parallel execution. Only re-runs what has changed since the last analysis.

**The lenses are the always-on floor; they are the source of truth.** The lens
subagents ALWAYS produce the analysis artifacts — `$ARTIFACTS_DIR/{survey,
architecture,domain,technical,ops}.md` plus their manifest sidecars — by reading
the repo at HEAD. That is the accurate, current, certified output every
downstream step (forge, wiki, orient, `npx skills add`) consumes.

**wicked-brain is an opt-in, additive enricher — never a substitute.** When the
user passes `--enrich-from-brain` (default off) and a brain server is reachable,
the pipeline may, *after* the lens artifacts exist, append **supplementary design
rationale** the lenses cannot see (recorded ADRs, decisions, memories) as a
clearly-marked, separable addition. Brain never produces or replaces a lens
artifact and never overrides a lens fact — see *Step 3.5* and the HARD RULE.

This reverses an earlier "co-equal source" design that a controlled A/B
disproved: brain-sourced artifacts matched the lenses' *shape* only because an
LLM synthesis step reshaped them, and were materially **worse as a substitute**
on a Node repo — a stale index (a deleted docs/ADR tree), duplicate and
cross-repo-leaked chunks, and it **missed the two highest-value gotchas the
lenses caught**, so it would have fed actively-wrong guidance to the forge.
Brain earns its place as additive rationale, not as a source that can replace
what the lenses read from HEAD.

---

## HARD RULE — brain is opt-in additive rationale, never a runtime dependency and never the authoritative analysis

**The generated package — task skills, wiki skill, and the `CLAUDE.md` /
`AGENTS.md` context doc — MUST stay fully self-contained and run in any CLI
with no server running.** wicked-brain, when present and explicitly opted into,
only *appends supplementary rationale* during generation; it is never a
dependency of the *output*.

- **Brain is never the authoritative analysis.** The lens floor — read from
  HEAD — is the source of truth. Brain content is *additive rationale only*; on
  any conflict the **lens wins**. A controlled A/B proved brain worse as a
  substitute (stale index, missed the highest-value gotchas), so it may add to
  the lens analysis but never replace or "correct" it.
- The wiki refs are **materialized into the package as static files** by
  `repo-wiki-planner` exactly as on the (always-run) lenses path. Never emit a
  skill, wiki article, or context line that says "ask the brain at runtime" or
  that points at a brain server / endpoint.
- The lens artifacts are **identical in shape** whether or not enrichment ran:
  same files, same manifests, same generated skill folders, same router links.
  Enrichment only *appends* a clearly-marked, separable rationale section/sidecar.
- The brain server may be down (it often is on this machine), or enrichment may
  not be requested at all. Either case is normal, not an error — the lens floor
  is complete on its own and the run proceeds unchanged. A failed or empty brain
  query never blocks a run and never degrades the output.

If a change would make any generated artifact require a live brain to function,
or would let brain content overwrite a lens fact, it is wrong. Stop — the lenses
are the floor and the source of truth.

---

## Read the user's intent

No commands — infer what the user wants from their message.

| Intent | What to do |
|---|---|
| **First analysis** — "analyze this repo", "build the knowledge base" | Surveyor → all 4 lenses → ask which outputs (skill / wiki / both) |
| **Both outputs** — "do everything", "analyze and produce wiki and skill" | Full pipeline → skill-forge + wiki-planner in parallel |
| **Wiki only** — "generate the wiki", "build the docs" | Full pipeline → wiki-planner only |
| **Skill only** — "make me an agent skill" | Full pipeline → skill-forge only |
| **Refresh** — "update the analysis", "what changed?" | Freshness check → stale lenses only → re-run outputs |
| **Status** — "is the analysis fresh?", "what is stale?" | Freshness check → report only, no re-run |
| **Targeted** — "just analyze the architecture" | Run that lens independently, skip full orchestration |

If the repo path is not in the message, ask once before proceeding.

**Brain enrichment (opt-in, additive).** Orthogonal to intent above: the lenses
always produce the analysis. `--enrich-from-brain` (default **off**) asks the
pipeline to *additionally* append supplementary design rationale from
wicked-brain **after** the lens artifacts exist — see *Step 3.5*. It never
changes *which* lens artifacts are produced, *what* the lenses contain, or *what*
runs afterward; it only adds a separable rationale layer. Set it when the user
says "enrich from the brain" / "add the recorded decisions / ADRs". The default
(no flag) runs the lenses alone — the verified floor — and is what every prior
dogfood run used.

---

## Step 0 — Initialize the understanding store

Before doing anything else, determine the artifacts directory. Scripts ship in
their skill's `scripts/` directory — invoke them by the path to the installed
skill (no `$CLAUDE_PLUGIN_ROOT`). `init_understanding.py` is bundled with this
skill, so call it relative to this skill's directory:

```bash
ARTIFACTS_DIR=$(python3 scripts/init_understanding.py \
  init --repo-root "$REPO_ROOT")
```

This creates `~/.wicked-understanding/repos/{repo-key}/` and prints its path. All
lens artifacts, manifests, and the freshness check use `$ARTIFACTS_DIR`.
Artifacts use bare names (`survey.md`, `architecture.md`, …) — the store
directory is already per-repo, so no `{repo}-` prefix is needed.

---

## Step 1 — Check survey freshness

`check_freshness.py` is bundled with this skill — invoke it relative to this
skill's directory:

```bash
python3 scripts/check_freshness.py \
  --repo-root "$REPO_ROOT" \
  --artifacts-dir "$ARTIFACTS_DIR"
```

This outputs JSON like:
```json
{
  "survey":       { "status": "fresh|stale|missing", "reason": "..." },
  "architecture": { "status": "fresh|stale|missing", "reason": "..." },
  "domain":       { "status": "fresh|stale|missing", "reason": "..." },
  "technical":    { "status": "fresh|stale|missing", "reason": "..." },
  "ops":          { "status": "fresh|stale|missing", "reason": "..." }
}
```

Show the user a freshness summary before proceeding:
```
Survey:       fresh  (commit abc123, 2h ago)
Architecture: stale  (src/di/container.ts modified)
Domain:       stale  (src/models/order.ts added)
Technical:    fresh
Ops:          missing
```

---

## Step 2 — Run survey if needed

If `survey` is `stale` or `missing`, run `repo-surveyor` now (synchronously —
all lenses depend on the survey output).

---

## Step 3 — Determine which lenses to run

```
stale_lenses = [lens for lens, result in freshness if result.status != "fresh"]
```

In `full-pipeline` mode: run all 4 lenses regardless.
In `refresh` mode: run only stale/missing lenses.
With `--lenses` flag: run only the specified lenses.

If `stale_lenses` is empty: tell the user everything is fresh, suggest running
`repo-skill-forge` to regenerate the skill with current artifacts.

---

## Step 3.5 — Decide whether brain enrichment is even possible

Enrichment is a strictly *additive*, *post-lens* step. It does **not** branch
how the lenses run — the lenses always run and always produce the artifacts
(Step 4, below). All this step does is decide whether the optional enrichment in
*Step 4.5* can happen at all:

```
no --enrich-from-brain (default) → skip enrichment entirely; the lenses are the
                                    complete, certified output. Do NOT probe.
--enrich-from-brain              → run the probe; reachable → enrichment is
                                    possible (Step 4.5), unreachable → skip
                                    enrichment and say so. Never hard-fail.
```

The probe is the same deterministic script bundled with this skill — still used,
now only to decide whether enrichment is possible. Invoke it relative to this
skill's directory (no `$CLAUDE_PLUGIN_ROOT`):

```bash
python3 scripts/detect_brain.py
```

It prints JSON like `{"available": true, "url": "..."}` / `{"available": false,
"reason": "..."}`. Treat any non-zero exit, missing script, or `available:
false` as **enrichment not possible** — that is expected, not an error; the run
proceeds on the lens floor alone.

**Target the correct brain before trusting it.** The `--brain` flag is ignored
once a server already holds the port, so a reachable server may be bound to a
*different* repo's brain. Before using any brain result, confirm the reachable
server is bound to THIS repo's brain — check the server status `brain_path` /
port and that it matches this repo. If it is the wrong brain, treat enrichment
as not possible (do not enrich from another repo's knowledge — cross-repo
leakage was one of the A/B failure modes).

Whether or not enrichment is possible, **Step 4 always produces
`$ARTIFACTS_DIR/{lens}.md` + `{lens}.manifest.json` for every stale lens by
reading the repo**, and Step 5 onward consumes those as the source of truth.

---

## Step 4 — Run lenses (always; the source of truth)

This step is **unconditional** — the lens subagents always read the repo at HEAD
and produce, per stale lens, `$ARTIFACTS_DIR/{lens}.md` (matching the template
the lens skill defines) plus `$ARTIFACTS_DIR/{lens}.manifest.json` (the sidecar
that lets `check_freshness.py` detect staleness later). There is no brain branch
here; brain never produces a lens artifact.

The lens analyses are independent — each reads the shared survey and writes
to its own artifact file. Dispatch them as subagents.

### When parallel subagents are available (Claude Code, Cowork, most hosts)

Dispatch one subagent **per stale lens, all in a single batch** so they run
concurrently. Each subagent is self-contained — give it this brief:

```
Run the {lens} lens on the repository at {REPO_ROOT}.
The survey is already done — read it from {ARTIFACTS_DIR}/survey.md.
Follow the analysis instructions in (each lens skill installs alongside this
one — paths are relative to this skill's directory):
  ../{skill}/SKILL.md
  ../{skill}/references/{guide}
Write your output to:
  - {ARTIFACTS_DIR}/{lens}.md
  - {ARTIFACTS_DIR}/{lens}.manifest.json   (populate files_analyzed with
    every file you read; record git HEAD and per-file mtime/size)
```

| Lens | skill | guide |
|---|---|---|
| architecture | `repo-architect` | `references/architecture-guide.md` |
| domain | `repo-domain-analyst` | `references/domain-guide.md` |
| technical | `repo-tech-analyst` | `references/technical-guide.md` |
| ops | `repo-ops-analyst` | `references/ops-guide.md` |

Wait for the whole batch to finish before Step 5. If a lens agent fails,
record it and continue — see Error Handling.

### When subagents are NOT available (single-threaded host)

Run each stale lens yourself, sequentially, in order
architecture → domain → technical → ops (architecture first because domain
analysis can reference its findings). For each: load the lens skill's
SKILL.md, perform the analysis, write the artifact + manifest, confirm, move on.

---

## Step 4.5 — Enrich from the brain (opt-in; additive; never overrides a lens)

**Skip this entire step unless `--enrich-from-brain` was set AND Step 3.5
confirmed a reachable server bound to THIS repo's brain.** This is pure
addition: the lens artifacts from Step 4 are already complete and certified.
Enrichment only *appends* supplementary **design rationale** the lenses cannot
see from HEAD — recorded ADRs, decisions, and memories about *why* the code is
the way it is.

**Source brain content through the `wicked-brain:query` AGENT, never raw FTS.**
The agent does multi-query plus synthesis; the broad single-string FTS queries
an earlier design prescribed return **0 results** (the index is implicit-AND, so
a long query matches nothing). Ask focused rationale questions, e.g. *"What
recorded design decisions, ADRs, or trade-offs explain the architecture of
{REPO_NAME}? Cite the decision, not the code."*

Write the result as a **clearly-marked, separable addition** — never inline into
a lens's own sections. Two acceptable shapes (pick one, be consistent):

- Append a final section to the relevant lens artifact:
  `## Design rationale (from wicked-brain — may lag HEAD)`, OR
- Write a sidecar `$ARTIFACTS_DIR/{lens}.rationale.md` the forge / orient may
  cite.

**The lens wins on every conflict — these are non-negotiable rules:**

- Brain content **never overwrites, edits, or "corrects" a lens fact.** The lens
  read HEAD; the brain may lag it. Where they disagree, keep the lens value and
  drop (or flag) the brain claim.
- Everything brain-sourced lives **under the marked rationale heading/sidecar
  only**, so a reader (and the forge) can always tell lens-fact from brain-
  rationale and the lens artifact stays the source of truth.
- **Do not touch the lens manifests.** `{lens}.manifest.json` describes the
  files the lens read from HEAD; enrichment adds no files and changes no
  manifest, so freshness still tracks the real source.
- Treat brain content as **possibly-stale and possibly-cross-repo**: a
  controlled A/B found a stale index (a deleted docs/ADR tree), duplicate
  chunks, and cross-repo leakage. Include only what is clearly about THIS repo
  and clearly rationale (not a restatement of code the lens already covered),
  and flag it as may-lag-HEAD via the heading above.

If a query returns nothing useful, or the brain becomes unreachable mid-step,
simply skip enrichment for that lens — the lens floor is already the complete
output. Note in the Step 5 report which lenses got a rationale addition.

---

## Step 5 — Report and optional post-steps

After all lenses complete, report the lens artifacts (always lens-produced) and,
if enrichment ran, which lenses got an appended rationale section:
```
Analysis complete:
  ✓ Architecture  → architecture.md  (52 lines)  [+ brain rationale]
  ✓ Domain        → domain.md        (67 lines)
  ✗ Technical     → skipped (fresh)
  ✓ Ops           → ops.md           (38 lines)
  enrichment: --enrich-from-brain → brain reachable (this repo's brain);
              appended design rationale to architecture only
```
On a default run (no `--enrich-from-brain`), omit the enrichment line entirely —
the lenses are the complete output.

Then run the requested post-steps. If both are requested, dispatch them as
two subagents in the same batch — they are independent:

| Intent | Runs | Output |
|---|---|---|
| skills | `repo-skill-forge` | task skills in `$ARTIFACTS_DIR/skills/` |
| wiki | `repo-wiki-planner` | wiki skill in `$ARTIFACTS_DIR/skills/wiki/` + viewer |
| both | forge + wiki, dispatched together | both outputs |

Once the forge and/or wiki have written into `$ARTIFACTS_DIR/skills/`, validate
the package, then install it into the user's agent CLI(s).

**Final step before install — validate the package installs.** `npx skills`
silently drops any skill whose frontmatter it can't parse (exit 0, never
installed) — the classic cause is a plain-scalar `description:` containing `: `
("Nested mappings are not allowed in compact mappings"). A skill the tool can't
parse is silently dropped, so this count check is **mandatory** before
`npx skills add … --all`:

```bash
npx -y skills add "$ARTIFACTS_DIR/skills" --list
```

Confirm the "Found N skill(s)" it reports EQUALS the number of skill folders
generated under `$ARTIFACTS_DIR/skills/` (count them:
`ls -d "$ARTIFACTS_DIR"/skills/*/ | wc -l` — every task skill plus the wiki). If
N is fewer, the package has invalid frontmatter — **FAIL loudly, name which
folder(s) were dropped** (those absent from the `--list` output), fix that
frontmatter (make `description:` a folded block scalar `>`), and re-run the
check. Do **not** install a partial package.

Once the count matches, install the whole generated package with ONE command —
the orchestrator runs it, the user does not:

```bash
npx skills add "$ARTIFACTS_DIR/skills" --all
```

Run it once after both forge and wiki complete so the task skills and the wiki
install together (they are siblings under `$ARTIFACTS_DIR/skills/`).

### Final step — orient agents (repo-orient)

Once the package is installed, dispatch `repo-orient` to write the
always-in-context context doc (`CLAUDE.md` / `AGENTS.md`; `GEMINI.md` if used)
into the analyzed repo — distilled from the lenses and **routing to the skills
just installed**. This is the keystone of the token economy: the next session
starts oriented in ~50 lines, pointed at the curated skills/wiki instead of
re-exploring. Merge-safe (a managed block — never clobbers hand-written rules),
so it's safe to run on every refresh.

If no post-step was specified, offer:
```
Ready. What next?
  → repo-skill-forge   — task workflow skills, installed via npx skills add
  → repo-wiki-planner  — wiki skill + viewer, installed via npx skills add
  → repo-orient        — CLAUDE.md / AGENTS.md that routes agents to the above
  → all                — generate, install, and orient (recommended)
```

### Wiki refresh awareness

When running `refresh --wiki`, pass the updated lens names to
`repo-wiki-planner`. It maps each lens to the article types it feeds
and only regenerates articles whose source artifacts changed.

---

## Freshness Logic Details

The freshness check uses git when available, falling back to mtime.

**Git-based check** (preferred):
1. Read `generated_at` and `git_commit` from manifest
2. Run: `git -C <repo> log --name-only --format="" {commit}..HEAD -- {watch_patterns}`
3. If any files in the output overlap with `files_analyzed`, status = `stale`
4. If `git_commit` is null or not found in history, status = `stale`

**Mtime-based fallback**:
1. For each file in `files_analyzed`, compare stored `mtime` with current
2. If any file's current mtime differs by > 1 second, status = `stale`
3. If any `watch_pattern` glob now matches files not in `files_analyzed`, status = `stale`

A lens is also `stale` if the survey itself was regenerated after the lens ran
(lens `generated_at` < survey `generated_at`).

---

## Why agent dispatch, not subprocess scripts

Lens analysis, skill generation, and wiki-article generation are all LLM
work, so the orchestrator dispatches them as subagents using the host's
native parallel-agent mechanism — it does **not** shell out to `claude -p`.
That keeps the pipeline host-agnostic (works wherever subagents work, with a
clean sequential fallback), observable, and free of a CLI-on-PATH dependency.

Only deterministic mechanics stay as scripts: `init_understanding.py` (store
keying), `check_freshness.py` (git-diff / mtime), `assemble_wiki_skill.py`
(router templating), `generate_viewer.py` (HTML build), and `detect_brain.py`
(the brain reachability probe — a pure availability check that prints JSON, no
LLM; still used, now to decide whether opt-in enrichment is possible). The
optional brain *enrichment* is not a script either: rationale is pulled through
the `wicked-brain:query` agent (multi-query + synthesis — raw broad FTS returns
0), keeping the "scripts never call an LLM" rule intact.

---

## Error Handling

If a lens agent fails:
- Mark it as failed in the report: `✗ {lens} → FAILED: {error}`
- Continue with the other lenses — they are independent
- Still offer to forge / build the wiki from the successful artifacts

If the survey fails: abort — all lenses depend on it.

If the brain is unreachable, bound to the wrong repo, or errors mid-step (probe
says unavailable, `detect_brain.py` missing, or a `wicked-brain:query` errors):
this is **not a failure** — simply skip the opt-in enrichment (Step 4.5) and say
so. The lens artifacts from Step 4 are already the complete, certified output;
enrichment is additive only, so its absence never blocks a run and never changes
the output's shape.

If a single brain query returns nothing useful: skip enrichment for that lens
(Step 4.5) and keep any rationale that did come back for the others. The lens
floor stands on its own either way.
