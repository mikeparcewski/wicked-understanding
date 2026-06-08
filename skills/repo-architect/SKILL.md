---
name: repo-architect
description: >
  Analyze the architecture of a code repository — component structure, layering, data flow, dependency direction, and cross-cutting concerns. Run independently whenever someone wants to understand how a codebase is structured, needs an architecture diagram, or wants to review architectural patterns. Requires a survey (run repo-surveyor first if `survey.md` doesn't exist). Writes `architecture.md` and a manifest sidecar so repo-analyst can detect when this lens needs refresh.
---

# repo-architect

**Watches**: entry points, DI/container/registry, interfaces/protocols, routers,
middleware chains, event bus integrations, ORM/DB config.

**Outputs**: `architecture.md` + `architecture.manifest.json`

---

## Prerequisites

Load `survey.md` from the artifacts directory. If it doesn't exist, run `repo-surveyor` first.

---

## Analysis process

Read `references/architecture-guide.md` for the full file-reading strategy
and what to look for in each file category.

**Priority reading order:**
1. Entry points & bootstrap files (from survey)
2. DI container / provider / module registry
3. Interface / protocol / abstract base class definitions
4. Router / dispatcher / handler registry
5. Middleware or filter chains
6. Event bus / message broker integration (if any)
7. ORM / repository configuration

---

## Output

**Artifacts directory**: `~/.wicked-understanding/repos/{repo-key}/` — get it via
`init_understanding.py path --repo-root "$REPO_ROOT"` (see repo-surveyor for the
full invocation). Files use bare names.

## Output files: `architecture.md`

```markdown
# Architecture: {repo-name}

**Generated**: {ISO datetime}

## Style

{Architectural style} — {2-sentence explanation}

## Component Map

{ASCII or Mermaid diagram — major components + communication paths}

Example:
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│ HTTP Router │────▶│ Handler Layer   │────▶│ Service Layer│
│ src/routes/ │     │ src/handlers/   │     │ src/services/│
└─────────────┘     └─────────────────┘     └──────┬───────┘
                                                    │
                                            ┌───────▼───────┐
                                            │ Domain Layer  │
                                            │ src/domain/   │
                                            └───────┬───────┘
                                                    │
                                            ┌───────▼───────┐
                                            │  Repositories │
                                            │ src/repos/    │
                                            └───────────────┘

## Layers

| Layer | Responsibility | Key path(s) |
|---|---|---|
| {e.g. Transport} | {what it handles} | `{path}` |

## Data Flow

Trace of a typical request from entry to storage:

1. **{Step name}** (`{file}`): {what happens here}
2. ...

## Cross-Cutting Concerns

| Concern | Location | Mechanism |
|---|---|---|
| Authentication | `{file}` | {middleware / decorator / ...} |
| Authorization | `{file}` | {RBAC / policy / ...} |
| Input validation | `{file}` | {library + approach} |
| Error handling | `{file}` | {normalize to / error classes} |
| Logging | `{file}` | {structured / level-based} |
| Caching | `{file or none}` | {strategy} |

## Dependency Direction

{Is it clean? Inward-facing? Any inversions or circular deps? Be specific.}

## Key Architectural Decisions

{2–4 notable decisions — why things are structured this way, inferred or documented}

## Architectural Gotchas

{Non-obvious coupling, order-dependent initialization, hidden globals, etc.}
- {Gotcha}: {file}
```

---

## Output: `architecture.manifest.json`

```json
{
  "lens": "architecture",
  "repo_root": "<absolute path>",
  "repo_name": "<name>",
  "generated_at": "<ISO datetime>",
  "git_commit": "<SHA or null>",
  "watch_patterns": [
    "src/index.*", "src/main.*", "src/server.*",
    "src/di/**", "src/container.*", "src/providers/**", "src/*Module.*",
    "src/interfaces/**", "src/ports/**", "src/contracts/**",
    "src/routes.*", "src/router.*", "src/handlers/**",
    "src/middleware/**", "src/filters/**",
    "src/events/**", "src/bus.*",
    "src/db/**", "src/database/**", "ormconfig.*"
  ],
  "files_analyzed": [
    { "path": "<relative path>", "mtime": 0.0, "size_bytes": 0 }
  ]
}
```

Adapt `watch_patterns` to the actual paths found in this repo.
