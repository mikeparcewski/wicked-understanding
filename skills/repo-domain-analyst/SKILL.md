---
name: repo-domain-analyst
description: >
  Analyze the functional domain and business logic of a code repository — entities, operations, invariants, workflows, and external integrations. Run independently when someone needs to understand what a system does (not how it's built), review domain logic, or map business rules. Requires a survey; run repo-surveyor first if needed. Writes `domain.md` and a manifest sidecar. Trigger on phrases like "what does this system do", "explain the business logic", "what are the domain entities", "how does the billing/auth/ordering work".
---

# repo-domain-analyst

**Watches**: models, entities, services/use-cases, schemas, validators,
state machines, seed data, integration tests, API routes (as feature index).

**Outputs**: `domain.md` + `domain.manifest.json`

---

## Prerequisites

Load `survey.md` from the artifacts directory. If it doesn't exist, run `repo-surveyor` first.

---

## Analysis process

Read `references/domain-guide.md` for detailed strategies.

**Priority reading order:**
1. Domain model / entity files (`models/`, `entities/`, `domain/`)
2. Schema / type definitions (`*.schema.ts`, `schemas.py`, `*.proto`, `types.go`)
3. Service / use-case files (business operations)
4. Validation logic (encodes domain rules explicitly)
5. State machine or workflow files (lifecycle logic)
6. API route list (feature inventory — breadth only)
7. Seed data / fixtures (real examples of domain objects)
8. Integration/acceptance tests (often read like specs)

---

## Output

**Artifacts directory**: `~/.wicked-understanding/repos/{repo-key}/` — get it via
`init_understanding.py path --repo-root "$REPO_ROOT"` (see repo-surveyor for the
full invocation). Files use bare names.

## Output files: `domain.md`

```markdown
# Domain Model: {repo-name}

**Generated**: {ISO datetime}

## Domain Summary

{2–3 sentences: what problem space, who the users are, what the core job is}

## Core Entities

### {EntityName}
- **Represents**: {real-world concept}
- **Key attributes**: `{field1}`, `{field2}`, `{field3}`
- **Lifecycle / States**: {none | `draft → active → archived` | etc.}
- **Relationships**: {has-many X, belongs-to Y, etc.}
- **File**: `{path}`

(Top 5–10 entities)

## Core Operations

### {OperationName}
- **Trigger**: {user action / API call / event / schedule}
- **Actor**: {who initiates}
- **Inputs**: {key parameters}
- **Business rules**: {list the rules enforced}
- **Side effects**: {what gets persisted / emitted / notified}
- **File**: `{path}`

(Top 8–12 operations)

## Domain Rules & Invariants

Constraints enforced in code:
- {Rule description} — `{file}:{approx line}`
- ...

## Key Workflows

### {WorkflowName}
{Multi-step process description}
1. {Step 1}
2. {Step 2}
...

## External Integrations

| Service | Purpose | Direction | File |
|---|---|---|---|
| {e.g. Stripe} | Payments | outbound | `{path}` |
| {e.g. SendGrid} | Email | outbound | `{path}` |
| {e.g. Webhooks} | Events | inbound | `{path}` |

## Domain Glossary

| Term | Definition in this codebase |
|---|---|
| {term} | {definition — specific to this codebase, not generic} |
```

---

## Output: `domain.manifest.json`

```json
{
  "lens": "domain",
  "repo_root": "<absolute path>",
  "repo_name": "<name>",
  "generated_at": "<ISO datetime>",
  "git_commit": "<SHA or null>",
  "watch_patterns": [
    "src/models/**", "src/entities/**", "src/domain/**",
    "src/schemas/**", "src/types/**", "*.schema.ts",
    "src/services/**", "src/use-cases/**", "src/usecases/**",
    "src/validators/**", "src/validation/**",
    "src/workflows/**", "src/state/**",
    "migrations/**", "db/schema.*",
    "test/fixtures/**", "test/factories/**"
  ],
  "files_analyzed": [
    { "path": "<relative path>", "mtime": 0.0, "size_bytes": 0 }
  ]
}
```

Adapt `watch_patterns` to actual paths found in this repo.
