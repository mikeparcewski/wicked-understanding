```
           _      __            __
 _      __(_)____/ /_____  ____/ /
| | /| / / / ___/ //_/ _ \/ __  /
| |/ |/ / / /__/ ,< /  __/ /_/ /
|__/|__/_/\___/_/|_|\___/\__,_/

                   __               __                  ___
  __  ______  ____/ /__  __________/ /_____ _____  ____/ (_)___  ____ _
 / / / / __ \/ __  / _ \/ ___/ ___/ __/ __ `/ __ \/ __  / / __ \/ __ `/
/ /_/ / / / / /_/ /  __/ /  (__  ) /_/ /_/ / / / / /_/ / / / / / /_/ /
\__,_/_/ /_/\__,_/\___/_/  /____/\__/\__,_/_/ /_/\__,_/_/_/ /_/\__, /
                                                              /____/
```

**Turn any repo into installable agent skills + a routing `CLAUDE.md`.** Your
agent CLI wakes up oriented in ~50 curated lines instead of re-reading the whole
codebase every session. No server. No embeddings. No lock-in.

```bash
npx skills add mikeparcewski/wicked-understanding --all
```

(`--skill repo-analyst` installs just one; the per-repo skills it *generates*
install the same way — the pipeline runs `npx skills add` for you.)

Works with **Claude Code**, **Gemini CLI**, **Cursor**, **Codex**, and **Copilot
CLI** — anything the [`skills`](https://agentskills.io) standard targets. Dogfooded
on four real repos: Python, Node, a large TypeScript monorepo, and Go.

---

## The problem

Every session, your agent wakes up blank and rediscovers the same repository —
grepping, opening files, rebuilding the mental model you already paid for
yesterday. On a large codebase that's thousands of tokens and several minutes
before it does anything useful, and it happens *again* in the next session, the
next chat, a teammate's CLI.

The usual fix is hand-written docs — which rot the moment the code moves, so the
agent learns to distrust them. The knowledge stays trapped: rebuilt per session,
per agent, per tool.

## What you get instead

Analyze the repo **once**. Focused lenses (architecture, domain, technical, ops)
read the code at HEAD and turn it into three things your agent actually loads:

- **Task skills** — `fix-bug`, `add-feature`, `add-domain`, `write-tests`,
  `scaffold` — each grounded in *this* repo's real files, commands, and gotchas
  (symptom→file triage, the exact wiring step, the trap that causes the 404).
  Not generic advice; scaled to the repo's size.
- **A wiki** — an agent-loadable knowledge base plus a standalone HTML viewer,
  pulled in on demand when a task needs the deep context.
- **A routing `CLAUDE.md` / `AGENTS.md`** — the always-in-context keystone: ~50
  lines that orient any session and point it at the skills above instead of
  re-exploring. Merge-safe — it augments a managed block and never clobbers your
  hand-written rules.

Everything installs via `npx skills` and is **self-contained** — no daemon, no
vector DB, no `$CLAUDE_PLUGIN_ROOT`, no Claude-only lock-in. The lenses read HEAD,
so the analysis is *current*, not a stale doc; re-run after changes and only what
moved is refreshed.

> Optional: if you run [wicked-brain](https://github.com/mikeparcewski), point
> `repo-analyst --enrich-from-brain` at it to fold in design rationale (ADRs,
> decisions) the code alone can't show. It's additive only — the lenses stay the
> source of truth, and nothing it produces needs a server at runtime.

---

## Skills

| Skill | Role | Watches | Output |
|---|---|---|---|
| `repo-surveyor` | Mandatory first step | whole repo | `survey.md` + manifest |
| `repo-architect` | Lens | entry points, DI, interfaces, routers | `architecture.md` + manifest |
| `repo-domain-analyst` | Lens | models, services, schemas, validators | `domain.md` + manifest |
| `repo-tech-analyst` | Lens | source files, tests, lint config | `technical.md` + manifest |
| `repo-ops-analyst` | Lens | Dockerfile, CI, Makefile, .env | `ops.md` + manifest |
| `repo-analyst` | **Orchestrator** | manifests → re-runs stale lenses | refreshed artifacts |
| `repo-skill-forge` | Post-analysis | all artifacts | task-skill package |
| `repo-wiki-planner` | Post-analysis | all artifacts | wiki skill + viewer |
| `repo-orient` | Post-analysis (last) | artifacts + generated skills | merge-safe `CLAUDE.md`/`AGENTS.md` routing to them |

## Pipeline

```
[repo path]
     │
     ▼
surveyor ─────────────────────────────────────────── survey.md
     │
     ▼  (analyst dispatches one agent per lens, in parallel)
┌────┴───────────────────────────────────────┐
│  architect  → architecture.md               │
│  domain     → domain.md                      │
│  tech       → technical.md                   │
│  ops        → ops.md                         │
└─────────────────────────────────────────────┘
     │
     ▼  (analyst dispatches forge + wiki, in parallel)
┌────┴────────────────────────────────────────────────────────────┐
│  forge → fix-bug/ add-feature/ …   wiki → wiki/ (router + refs/) │
│     ↓ both emit into  ~/.wicked-understanding/repos/{key}/skills/ │
│     ↓ pipeline runs:  npx skills add <that path> --all           │
│  → installed into your agent CLI(s)   (+ viewer.html on demand)  │
└──────────────────────────────────────────────────────────────────┘
```

## Analysis backend

The **lenses always run and are the source of truth** — they read HEAD, so the
analysis is accurate and current. wicked-brain is an **opt-in build-time
enricher** (`repo-analyst --enrich-from-brain`): when its server is reachable it
*adds* supplementary design rationale (ADRs, recorded decisions) the lenses can't
see, in a separate marked section — it never replaces a lens artifact or
overrides a lens fact. Brain is never a runtime dependency; the output is the
same self-contained, cross-CLI `npx skills` package either way.

An A/B against a live brain settled this: brain as a *substitute* source was
worse — it served a stale, since-deleted docs/ADR tree and missed the sharpest
gotchas the lenses caught — so the lenses stay the floor and brain stays additive.

## Typical workflows

| You say… | What runs |
|---|---|
| "analyze this repo" | surveyor → 4 lenses → asks which output(s) |
| "analyze and build the wiki and skills" | full pipeline → forge + wiki in parallel |
| "generate the wiki" / "build docs" | full pipeline → wiki only |
| "build the dev skills" | full pipeline → forge only |
| "refresh the analysis" / "what changed?" | freshness check → re-run only stale lenses |
| "show me the wiki" / "open the viewer" | regenerate `viewer.html` from current refs |

You can also invoke any skill directly — e.g. "run repo-architect on /path" —
as long as a survey exists.

## Progressive loading

Task skills carry only what's needed to *start* a task (triage tables,
implementation sequences, command cheatsheets — under ~120 lines). Each ends
with a "Load for deeper context" table pointing into `../wiki/refs/` (the wiki
skill installs alongside them), so the agent pulls deeper knowledge
(`arch.md`, `domain.md`, `api.md`, `onboard.md`, …) only when the step needs it.

## Diff awareness

Every lens writes a `*.manifest.json` sidecar recording the git commit, watch
patterns, and the files it actually read. `check_freshness.py` runs
`git diff {commit}..HEAD` filtered to each lens's watch patterns (falling back
to mtime when git is unavailable). Only stale or missing lenses re-run. The
wiki planner maps lens changes to article types and regenerates only the
affected articles.

## Architecture: agents vs. scripts

The pipeline draws a hard line between LLM work and deterministic mechanics:

- **LLM work is dispatched as subagents** by the orchestrator using the host's
  native parallel-agent mechanism (with a sequential fallback). This covers the
  4 lens analyses, the selected task-skill generations, and the N wiki-article
  generations. No `claude -p` subprocesses — the pipeline is host-agnostic and
  needs no CLI on PATH.
- **Deterministic mechanics stay as Python scripts** (no LLM judgment,
  token-free, repeatable):
  - `repo-analyst/scripts/init_understanding.py` — store keying + index
  - `repo-analyst/scripts/check_freshness.py` — git-diff / mtime freshness
  - `repo-wiki-planner/scripts/assemble_wiki_skill.py` — router templating
  - `repo-wiki-planner/scripts/generate_viewer.py` — standalone HTML viewer

Each script ships in its skill's `scripts/` directory and is invoked by path
relative to the installed skill (no `$CLAUDE_PLUGIN_ROOT` dependency). Python 3
stdlib only.

## Storage

```
~/.wicked-understanding/
├── index.json                       # all analyzed repos
└── repos/{repo-key}/                # keyed by git remote (or dir name)
    ├── meta.json
    ├── survey.md        + survey.manifest.json
    ├── architecture.md  + architecture.manifest.json
    ├── domain.md        + domain.manifest.json
    ├── technical.md     + technical.manifest.json
    ├── ops.md           + ops.manifest.json
    ├── skills/                       # generated package → npx skills add
    │   ├── fix-bug/ add-feature/ … (per the size-scaling rule)
    │   └── wiki/ (SKILL.md + refs/)
    └── viewer.html                   # regenerated on demand
```

Files use bare names because the directory is already per-repo. Generated
skills are staged under `skills/` and installed into your agent CLI(s) by the
pipeline (`npx skills add`), not written into the analyzed repo's tree.

## Wiki article types

| Article type | ref file | Generated when |
|---|---|---|
| `product-overview` | `overview.md` | always |
| `onboarding-maintainer` | `onboard.md` | always |
| `domain-reference` | `domain.md` | domain has ≥ 1 core entity |
| `architecture-overview` | `arch.md` | ≥ 2 components found |
| `api-reference` | `api.md` | API surface identified |
| `capability` (×1–5) | `cap-{feature}.md` | ≥ 3 operations in domain |
| `concept-explanation` (×1–5) | `concept-{term}.md` | ≥ 3 glossary terms |
| `design-pattern` | `patterns.md` | ≥ 2 recurring patterns |
| `runbook` (×1–3) | `ops.md` | multi-step ops procedures |
| `agent-roster` | `agents.md` | agentic repo detected |

Every article follows the wiki output contract (purpose-prefixed slugs,
canonical IDs, strict H2 anchor order, file-based `[src: …]` citations, a
5-rule lint self-check, and an Evidence / Open Questions / Confidence closer).
The `slug` is the article's wiki-system identity; the `ref_file` is the stable
on-disk name the wiki router and task skills load.
