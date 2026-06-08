# Article Types — Content & Mapping Guide

Reference for `repo-wiki-planner`. Read the section for your article type
before generating. Each section defines: when to generate, source mapping,
required sections with content sources, confidence rubric, and slug pattern.

---

## Canonical ref_file set (single source of truth)

`slug` is the article's wiki identity (frontmatter + canonical IDs). `ref_file`
is the on-disk filename the router (`assemble_wiki_skill.py`) and the generated
task skills load. This table is the single source of truth for those on-disk
names — never hardcode a ref filename in a consumer; assign it from here.

| Article type | ref_file |
|---|---|
| product-overview | `overview.md` |
| architecture-overview | `arch.md` |
| api-reference | `api.md` |
| onboarding-maintainer | `onboard.md` |
| domain-reference | `domain.md` |
| design-pattern | `patterns.md` (`pattern-{name}.md` if > 1) |
| runbook | `ops.md` (`runbook-{op}.md` if > 1) |
| agent-roster | `agents.md` |
| capability | `cap-{feature-kebab}.md` |
| concept-explanation | `concept-{term-kebab}.md` |

---

## Table of Contents

1. [product-overview](#product-overview)
2. [onboarding-maintainer](#onboarding-maintainer)
3. [architecture-overview](#architecture-overview)
4. [domain-reference](#domain-reference)
5. [api-reference](#api-reference)
6. [capability](#capability)
7. [concept-explanation](#concept-explanation)
8. [design-pattern](#design-pattern)
9. [runbook](#runbook)
10. [agent-roster](#agent-roster)

---

## product-overview

**When**: always — if survey.md exists.
**Slug**: `{repo}-overview`
**Audience**: both
**Canonical IDs**: `{REPO}-OVERVIEW`
**Sources**: survey.md (primary), domain.md (secondary)
**Confidence**: 0.85 if both sources available; 0.65 if domain.md missing.

### Section mapping

**`## Purpose`**
What this page owns: "The {repo-name} product overview — who it's for, what
it does, and how the pieces fit together."

**`## Contract`** — formatted as sub-sections:

#### Elevator Pitch
← survey.md "Purpose & Context" (2–3 sentences max).
Start with a noun phrase: "{repo-name} is a {type} that {does X} for {audience}."
No marketing adjectives.

#### Who It's For
← survey.md "Type" + domain.md "Domain Summary".
Evidence table:

| Audience | Pain they bring | How this addresses it |
|---|---|---|
| {role} | {specific pain} | {observable outcome} |

Minimum 2 rows. Infer roles from the domain and type if not stated explicitly.

#### What It Does
← domain.md "Core Operations" (top 4–8, user-facing framing).
Evidence table:

| Capability | What the user does | Evidence |
|---|---|---|
| {User-facing name} | {Imperative, observable} | `[src: file:{path}]` |

Use domain operations as source. Frame as user-facing outcomes, not internal
mechanism ("Store and retrieve session turns" not "Writes to `agent_sessions` table").
Evidence column: file path from domain.md analysis.

#### How It Works at a Glance
← architecture.md "Component Map" (simplified).
One Mermaid diagram (4–6 nodes). Follow with 2–4 sentences citing each box.
Use `[src: file:{path}]` for every named component.

If architecture.md is unavailable, use survey.md "Repository Structure" to
infer a simple flow.

#### Data Vocabulary
← domain.md "Core Entities" (top 5–8).
Evidence table:

| Entity | One-line definition | Evidence |
|---|---|---|
| {Name} | {definition specific to this repo} | `[src: file:{path}]` |

#### Known Gaps
← domain.md "Open Questions" + survey.md "Notable Observations".
Plain list. What users reasonably expect but the system doesn't do. No "planned for Q3".

---

## onboarding-maintainer

**When**: always — if ops.md exists.
**Slug**: `{repo}-onboarding-maintainer`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-ONBOARDING-MAINTAINER`
**Sources**: ops.md (primary), survey.md (secondary)
**Confidence**: 0.85 if ops.md is fully populated; 0.65 if commands are incomplete.

### Section mapping

**`## Purpose`**
"Zero-to-productive setup guide for a new {repo-name} contributor."

**`## Contract`** — formatted as sub-sections:

#### Welcome
← survey.md "At a Glance" (type, stack).
State: who this is for, what they'll accomplish, realistic time estimate.
No "happy coding" or "welcome aboard".

#### Prerequisites
← ops.md "Prerequisites" table.
One bullet per tool: name, minimum version, where to get it.
Mark optional prerequisites explicitly.

#### Setup Procedure
← ops.md "First-Time Setup" verbatim (already formatted as numbered steps).
Every step: imperative verb + copy-pasteable command + expected result.
Cite each command's source script: `[src: file:{path}]`.

#### First Successful Operation
← ops.md "Daily Development Commands" — pick the dev server start + health check.
Concrete: "Run {dev-command}, hit http://localhost:{port}/health, expect {response}."

#### Verification
← ops.md "Daily Development Commands".
Named observables: exit code, log line, URL response, file presence.

#### What To Explore Next
← suggest sibling articles from this wiki batch (slug links).
Link to `architecture-overview`, `api-reference`, capability articles.
Only link slugs that exist in the current batch.

#### Common Setup Problems
← ops.md "Common Issues & Fixes" (first 5 rows max).
Format: **symptom** → **fix**.
If ops.md has > 5 issues, include the top 5 by frequency and note "see ops guide for more".

**`## Invariants`**
← ops.md "Key Environment Variables" — required vars that must be set.
Each invariant: "The `{VAR}` environment variable must be set before starting the server."

**`## Gotchas`**
← ops.md "Common Issues & Fixes" (items that are non-obvious, not just missing deps).
2–4 sentences each.

---

## architecture-overview

**When**: if architecture.md is available and has ≥ 2 identified components.
**Slug**: `{repo}-architecture`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-ARCH`, `{REPO}-ARCH-LAYERS`
**Sources**: architecture.md (primary)
**Confidence**: 0.85 if architecture.md is complete; 0.65 if component map is thin.

### Section mapping

**`## Purpose`**
"The {arch-style} architecture of {repo-name}: component map, layers,
dependency direction, and cross-cutting concerns."

**`## Contract`** — formatted as sub-sections:

#### Component Map
← architecture.md "Component Map" (Mermaid diagram verbatim, then prose).
Every component named in prose: one `[src: file:{path}]` citation.

#### Layers
← architecture.md "Layers" table verbatim.
Add `[src: file:{path}]` to the Key path column if not present.

#### Data Flow
← architecture.md "Data Flow" numbered list verbatim.
Each step cites the file.

#### Cross-Cutting Concerns
← architecture.md "Cross-Cutting Concerns" table verbatim.

**`## Invariants`**
← architecture.md "Dependency Direction" and "Key Architectural Decisions".
Each invariant is a single sentence: "Domain layer imports MUST NOT reference
infrastructure layer modules. `[src: file:src/domain/]`"

**`## Gotchas`**
← architecture.md "Architectural Gotchas" verbatim.
Each gotcha: 2–4 sentences with citation.

**`## See also`**
← link to `api-reference`, `capability` articles, `design-pattern` if generated.

---

## domain-reference

**When**: whenever domain.md has ≥ 1 Core Entity — i.e. nearly always for a
system with durable data.
**Slug**: `{repo}-domain-reference`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-DOMAIN`
**Sources**: domain.md (primary)
**Confidence**: 0.85 if domain.md has populated Core Entities, Domain Rules &
Invariants, and a Glossary; 0.65 if any of the three is empty or inferred.

This is the maintainer-facing entity/rules/vocabulary reference. It is distinct
from `product-overview`: product-overview is the user-facing "what it does";
domain-reference is the canonical list of Core Entities (name, what each
represents, key attributes, lifecycle), the Domain Rules & Invariants, and the
Glossary — each file-cited. Where the two overlap (entity names, a one-line
definition), product-overview links here via `[src: {REPO}-DOMAIN]` rather than
restating the detail.

### Section mapping

**`## Purpose`**
"The domain reference for {repo-name}: the canonical entities, the rules that
constrain them, and the vocabulary — for a maintainer changing the model."

**`## Contract`** — formatted as sub-sections:

#### Core Entities
← domain.md "Core Entities" (the `### {EntityName}` H3 blocks).
One sub-section or table row per entity, preserving the H3 fields: what it
represents, key attributes, lifecycle/states, relationships. Cite each entity's
source file: `[src: file:{path}]` (from the entity's **File** field). Do not
drop the lifecycle — it is the field maintainers most need.

| Entity | Represents | Key attributes | Lifecycle | Evidence |
|---|---|---|---|---|
| {Name} | {real-world concept} | `{field}`, `{field}` | {`draft → active` or none} | `[src: file:{path}]` |

#### Domain Rules
← domain.md "Domain Rules & Invariants" (the constraint list).
One row per rule, framed as a stated constraint. Cite the file:line the rule
references. Rules that are properties the model MUST hold belong in
`## Invariants` below — keep this sub-section for the descriptive rule catalog.

| Rule | Enforced in |
|---|---|
| {constraint description} | `[src: file:{path}:{line}]` |

#### Glossary
← domain.md "Domain Glossary" table verbatim.
Each term: the definition as it means in THIS codebase, not the generic English
sense. Cite the entity or operation file where the term originates when known.

| Term | Definition in this codebase | Evidence |
|---|---|---|
| {term} | {repo-specific definition} | `[src: file:{path}]` |

**`## Invariants`**
← domain.md "Domain Rules & Invariants" — the rules that are properties the
model MUST always hold.
Each invariant: one sentence ending in a period, citing where it is enforced:
"An `{Entity}` MUST have a non-null `{field}` before it reaches `{state}`.
`[src: file:{path}:{line}]`"

**`## Gotchas`**
← domain.md rules and entity lifecycles that are non-obvious — states that look
terminal but aren't, attributes that mean something other than their name, a
relationship that is not enforced at the DB level.
2–4 sentences each, each citing its source.

**`## See also`**
← link to `product-overview` ({REPO}-OVERVIEW), `capability` articles that
operate on these entities, and `concept-explanation` articles for individual
glossary terms.

---

## api-reference

**When**: if technical.md "API Surface" section identifies an API (REST, GraphQL, gRPC, etc.).
**Slug**: `{repo}-api-reference`
**Audience**: both (one per audience if detail warrants it)
**Canonical IDs**: `{REPO}-API`
**Sources**: technical.md (primary), architecture.md (secondary)
**Confidence**: 0.75 — analysis gives patterns not exhaustive endpoint catalog.

### Section mapping

**`## Purpose`**
"The {protocol} API surface of {repo-name}: base URL, authentication,
endpoint conventions, and error handling."

**Note**: This generates a *patterns* reference, not an exhaustive endpoint catalog.
The analysis gives conventions and examples; it doesn't enumerate every endpoint.
Make this explicit: "For the full endpoint catalog, consult the OpenAPI spec at
`{path}` or the router files in `{path}`."

**`## Contract`** — formatted as sub-sections:

#### Surface
← technical.md "API Surface" — protocol, base path.
← architecture.md "Layers" transport layer.

#### Authentication
← technical.md "Conventions" (auth row) + architecture.md "Cross-Cutting Concerns" (auth row).
Name the scheme and cite the middleware: `[src: file:{path}]`.

#### Common Patterns
← technical.md "Conventions" table.
Request shape, response envelope, error response format.

#### Error Handling
← technical.md "Error Handling" section verbatim.
Status codes with conditions (not just "400 on error").

#### Adding a New Endpoint
← technical.md "Adding New Features → New API endpoint" verbatim.
This is often the most valuable part for a maintainer.

#### Rate Limits
← technical.md or ops.md rate limiting config. If none found: "(none — no rate
limiter registered)" with citation to where you verified this.

**`## Invariants`**
← technical.md "Non-Obvious Technical Details".
Each invariant: one sentence with file citation.

**`## Gotchas`**
← technical.md "Non-Obvious Technical Details" (non-obvious, not just conventions).

---

## capability

**When**: for each major feature in domain.md "Core Operations" with enough detail.
Cap at 5. Pick the top operations by: user impact, operational complexity, risk.
**Slug**: `{repo}-{feature-kebab}-capability`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-CAP-{FEATURE}`
**Sources**: domain.md (primary), architecture.md (secondary)
**Confidence**: 0.8 if entry points are identified; 0.6 if flow is inferred.

### Section mapping

**`## Purpose`**
"The {feature-name} capability: from user invocation through persisted outcome."

**`## Contract`** — formatted as sub-sections:

#### What It Does
← domain.md operation "Description" + "Side effects".
2–3 sentences. User-observable outcome — not implementation verbs.
"The user triggers X; the system responds with Y and emits Z."

#### Who Uses It
← inferred from domain.md operation "Actor" + "Trigger".
Bullet list: **Role** — when and why they invoke this.

#### Entry Points
← domain.md operation "Trigger" + "File".
Evidence table:

| Surface | Invocation | Handler |
|---|---|---|
| {API/UI/CLI} | {route or action} | `[src: file:{path}]` |

#### End-to-End Flow
← architecture.md "Data Flow" filtered to this capability's components +
  domain.md operation "Side effects".
Mermaid sequence or flow diagram. Then prose with one citation per component.

If architecture.md doesn't have per-capability flow, construct from:
- domain.md "Trigger" → entry point
- domain.md "Business rules" → service layer
- domain.md "Side effects" → persistence/events

#### Data It Touches
← domain.md entities involved in this operation + relationships.

| Source | Direction | Purpose | Citation |
|---|---|---|---|
| {entity/table} | read/write | {why} | `[src: file:{path}]` |

#### Business Rules
← domain.md operation "Business rules enforced" — formatted as invariants.
Each rule: one sentence with file citation.

**`## Invariants`**
← domain.md "Domain Rules & Invariants" filtered to this capability.

**`## Gotchas`**
← inferred from domain.md operation "Business rules" (the non-obvious ones).
Anything that would trip up a developer modifying this capability.

---

## concept-explanation

**When**: for each key term in domain.md "Domain Glossary" that appears in
≥ 2 operations. Cap at 5. Pick terms that would confuse a new developer.
**Slug**: `{repo}-{term-kebab}-concept`
**Audience**: both
**Canonical IDs**: `{REPO}-CONCEPT-{TERM}`
**Sources**: domain.md (primary)
**Confidence**: 0.7 — concepts are inferred from usage patterns.

### Section mapping

**`## Purpose`**
"What '{term}' means in {repo-name}: definition, lifecycle, and where it appears."

**`## Contract`** — formatted as sub-sections:

#### What It Is
← domain.md "Domain Glossary" entry for this term.
One noun phrase definition. Cite the entity or operation where it's defined.
Distinguish from the everyday English meaning if different.

#### Why It Exists
← inferred from domain.md operations that use this term.
One paragraph: what problem in THIS repo the concept solves.
If no clear reason is documented: state the inferred motivation and set confidence ≤ 0.6.

#### How It Works
← domain.md entity for this term (lifecycle, states, relationships).
For structural concepts: include a simple diagram.
For behavioral concepts: trace through the operations that use it.

#### Where It's Used
← domain.md operations referencing this term.

| Operation | Purpose | Citation |
|---|---|---|
| {OperationName} | {why it uses this concept} | `[src: file:{path}]` |

#### What It's Not
← identify the nearest neighbor concepts from domain.md that readers confuse with this.
At least one bullet: "This ≠ {OtherTerm}: {one-sentence distinction}."

**`## Gotchas`**
← non-obvious behaviors from domain.md rules that apply to this concept.

---

## design-pattern

**When**: if architecture.md identifies ≥ 2 recurring structural patterns
(Repository, BFF, Command Handler, etc.).
Write one article per pattern (not one article for all patterns).
**Slug**: `{repo}-{pattern-kebab}-pattern`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-PATTERN-{PATTERN}`
**Sources**: architecture.md (primary), technical.md (secondary)
**Confidence**: 0.8 if pattern has 3+ examples; 0.6 if 2 examples.

### Section mapping

**`## Purpose`**
"The {PatternName} pattern in {repo-name}: how to recognize it,
what instances exist, and how to add new ones."

**`## Contract`** — formatted as sub-sections:

#### Pattern Description
← architecture.md "Patterns in Use" row for this pattern.
What makes something an instance of this pattern. The structural signature.

#### Discovery Pattern (YAML)
← technical.md "Patterns in Use" + architecture.md.
The resolver-parseable YAML block (from wiki-docs `design_pattern` template):

```yaml
kind: design
call_targets:
  - {method that marks an instance}
file_globs:
  - {where instances live}
record_shape:
  id: symbol
  name: symbol.name
  file_path: symbol.file_path
```

#### Examples
← technical.md "Example file" for this pattern.
3–5 examples with `[src: file:{path}:{line}]` citations.

#### How to Add a New Instance
← technical.md "Adding New Features" adapted for this pattern.
Numbered steps.

**`## Invariants`**
← architecture.md "Dependency Direction" rules that apply to this pattern.

**`## Gotchas`**
← non-obvious things about this pattern in this specific codebase.

---

## runbook

**When**: for each significant operational procedure in ops.md that is multi-step
and recovery-oriented. Cap at 3. Focus on: "start the service", "run migrations",
"reset the database", "debug a failing build".
**Slug**: `{repo}-{operation-kebab}-runbook`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-RB-{OPERATION}`
**Sources**: ops.md (primary)
**Confidence**: 0.8 if commands are all present; 0.6 if any step lacks a command.

### Section mapping

**`## Purpose`**
"Step-by-step procedure for: {operation description}."

**`## Contract`** — formatted as sub-sections:

#### Situation
← name the trigger that brings someone to this runbook.
"Use when: {specific condition}."

#### Prerequisites
← ops.md "Prerequisites" filtered to what this operation needs.

#### Procedure
← ops.md commands for this operation, numbered.
Each step: imperative verb + copy-pasteable command + expected result.
Cite each: `[src: file:{path}]`.

#### Verification
← ops.md expected results for this operation.
Named observables: exit code, endpoint response, log line.

#### Rollback
← ops.md rollback steps if present; otherwise:
"(none documented — restore from backup or re-run from step 1)".

**`## Invariants`**
← ops.md environment variables required for this operation.

**`## Gotchas`**
← ops.md "Common Issues & Fixes" relevant to this operation.

---

## agent-roster

**When**: if survey.md "Notable Observations" or file tree contains SKILL.md,
`.claude/agents/`, `AGENTS.md`, or other agentic markers.
**Slug**: `{repo}-agent-roster`
**Audience**: maintainer
**Canonical IDs**: `{REPO}-AGENTS`
**Sources**: survey.md (primary), architecture.md if agentic patterns found
**Confidence**: 0.7 — agent metadata must be read from actual files.

### Section mapping

**`## Purpose`**
"The agent, skill, and command definitions in {repo-name}: what fires when."

**`## Contract`** — Agent Inventory table:

| Name | Trigger | Tools | Model tier |
|---|---|---|---|
| {name (kind)} | {when-to-use from frontmatter} | {tools list} | {model or "(unset)"} |

Populate from reading the actual agent/skill/command definition files found
during survey. Do not invent entries.

**`## Invariants`**
← any hardcoded trigger conditions or tool restrictions.

**`## Gotchas`**
← surprising trigger overlaps or tool inheritance patterns.

---

## Confidence rubric (all article types)

| Level | Condition |
|---|---|
| 0.85 | All source artifacts present; all required sections grounded; every citation traces to a real file found in the analysis |
| 0.75 | Minor gaps: 1–2 sections thin; 1–2 citations reference directories rather than specific files |
| 0.65 | Significant gap: a primary artifact was missing; key section is inferred rather than grounded |
| 0.5 | Multiple gaps; mark clearly in Open Questions |
| < 0.5 | Don't publish — save as draft and flag |
