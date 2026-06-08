# Wiki Skill Template

Template for the SKILL.md generated inside `{repo}-wiki/`.
This is what agents see. Keep the generated file under 150 lines.

---

## Frontmatter (generated)

```yaml
---
name: {repo}-wiki
description: >
  Living wiki for {repo-name} — a {type} built with {stack} that {purpose
  in one clause, e.g. "handles Stripe billing and subscription management"}.
  Contains: architecture ({arch-style} with {N} layers), domain model
  ({entity1}, {entity2}, {entity3}), {protocol} API ({base-path}, {auth-scheme}),
  maintainer onboarding, {N} capability deep-dives ({feature1}, {feature2}),
  and {N} operational runbooks.
  Load for any question about {repo-name}: architecture decisions, domain rules,
  API conventions, testing patterns, or how to add new features.
  Prefer this over raw file navigation — it synthesizes intent and patterns
  spread across dozens of files.
---
```

**Construction rules for the description:**
- Name the repo, type, and stack specifically
- List the key entities (from domain.md) — agents trigger on these names
- List key features (from domain.md operations)
- Include the arch style (from architecture.md)
- End with an explicit directive to use this over file navigation
- Total: 4-6 sentences, ~80-120 words

**Example (payments-service):**
```yaml
description: >
  Living wiki for payments-service — a Node.js/TypeScript REST API that handles
  Stripe billing, subscription lifecycle, and invoice generation. Contains:
  hexagonal architecture (4 layers: transport/application/domain/infrastructure),
  domain model (Subscription, Invoice, PaymentMethod, Customer entities), REST
  API (/api/v1/billing, JWT auth, Zod validation), maintainer onboarding,
  3 capability deep-dives (subscribe, generate-invoice, process-refund), and
  2 operational runbooks (run-migrations, debug-webhook). Load for any question
  about payments-service: billing logic, Stripe integration, subscription rules,
  or how to add new payment features. Prefer this over raw code navigation.
```

---

## Body structure (generated, keep under 150 lines total)

```markdown
# {Repo Name} Wiki

> {one-sentence purpose from survey.md}
> Generated: {date} | Stack: {stack} | Type: {type}

---

## Load guide

Read a ref only when you need it — they're detailed and long.

| I need to... | Load |
|---|---|
| Understand what this system is / does | `refs/overview.md` |
| Understand the architecture / components | `refs/arch.md` |
| Call or understand the API | `refs/api.md` |
| Set up a dev environment | `refs/onboard.md` |
| Understand how {feature1} works | `refs/cap-{feature1}.md` |
| Understand how {feature2} works | `refs/cap-{feature2}.md` |
| Understand what "{term1}" means | `refs/concept-{term1}.md` |
| Run a migration / debug a failure | `refs/ops.md` |

(Omit rows for article types not generated)

---

## Quick reference (no file load needed)

**Stack**: {stack}  |  **Type**: {type}  |  **~{N}k LOC**

### Dev commands
```bash
{install}     # install deps
{dev}         # start dev server → http://localhost:{port}
{test}        # run all tests
{migrate}     # run pending migrations
```

### Key entities

| Entity | What it is |
|---|---|
| `{Entity1}` | {one-line definition} |
| `{Entity2}` | {one-line definition} |
| `{Entity3}` | {one-line definition} |

(Top 5-7 from domain.md "Core Entities". One-line defs only — full detail in refs/overview.md)

### Key file locations

| What | Where |
|---|---|
| Entry point | `{path}` |
| Routes / handlers | `{path}` |
| Domain / services | `{path}` |
| Models / entities | `{path}` |
| Tests | `{path}` |
| DB migrations | `{path}` |

(From survey.md "Key Files" + architecture.md)

### Add new... (cheat sheet)

| To add... | Start at |
|---|---|
| API endpoint | `{path}` → follow `{ExampleHandler}` |
| Domain entity | `{path}` → then `{migration-command}` |
| Test | `{path}` → use `{FactoryName}` for fixtures |

(From technical.md "Adding New Features")

---

## Articles in this wiki

| Article | Audience | Confidence |
|---|---|---|
| Overview | both | {HIGH/MEDIUM/LOW} |
| Architecture | maintainer | {HIGH/MEDIUM/LOW} |
| API Reference | both | {HIGH/MEDIUM/LOW} |
| Onboarding | maintainer | {HIGH/MEDIUM/LOW} |
| {Feature1} Capability | maintainer | {HIGH/MEDIUM/LOW} |
| {Feature2} Capability | maintainer | {HIGH/MEDIUM/LOW} |
| {Term1} Concept | both | {HIGH/MEDIUM/LOW} |
| Operations & Runbooks | maintainer | {HIGH/MEDIUM/LOW} |
```

---

## Construction notes

**Quick reference section** is the highest-value part of the always-in-context body.
Agents use it constantly without loading any refs:
- Dev commands: from ops.md verbatim
- Key entities: from domain.md top 5-7; one-line defs only
- Key file locations: from survey.md + architecture.md
- Add new cheat sheet: from technical.md "Adding New Features"

**Load guide**: only include rows for article types actually generated.
Don't add placeholder rows for articles that were skipped.

**Articles table**: gives agents a mental model of what's available and
the confidence level, so they can calibrate how much to trust each ref.

**Total length target**: 80-150 lines. If you find yourself going longer,
trim the entities table (move detail to refs/overview.md) or trim the
file locations (keep only the 5 most-navigated paths).
