# Domain Analysis Guide

Reference for `repo-domain-analyst`. Read before starting analysis.

---

## Detect the stack first (the sources below are illustrative)

Where entities, rules, and operations live is stack- and shape-specific. From the
survey, fix: the language and how it models data (class, struct+interface,
struct+enum+trait, record, dataclass); whether the domain is OO (behavior on
objects) or functional/procedural (data types + free functions that transform
them); and whether there is a DB at all. The sources listed in each section are a
menu — use the ones the repo has. Never assume an ORM, validation library,
migrations, or a service layer the repo lacks; in a no-DB tool the "domain" may be
its core data types and the transformations over them, and that is a complete answer.

---

## Identifying Core Entities

An entity is a domain concept that has identity, state, and lifecycle — not
just a data bag. Distinguish from value objects (immutable, no identity). In a
functional codebase the same idea appears as the central data types the program
transforms, even without methods or identity; treat those as the domain model.

**Finding entities (by stack):**
- ORM model classes with IDs and timestamps (TS/Java/Python ORMs)
- Pydantic models / SQLAlchemy models / dataclasses (Python)
- TypeScript interfaces/classes in `models/` or `entities/`
- **Go**: `struct` types (often in a `model`/`domain` package) plus the
  `interface`s that operate on them; an entity frequently pairs a struct with a
  repository interface, but plenty are plain structs with no ORM.
- **Rust**: `struct`s and — importantly — `enum`s, which often model the domain's
  states/variants directly (e.g. an `enum Event { Created, Settled, .. }`); the
  `trait`s implemented for them describe behavior.
- Proto message types in `.proto` files (gRPC)

**For each entity, determine:**

1. **Identity**: what uniquely identifies it? (id, slug, composite key)

2. **Lifecycle/States**: look for `status`, `state`, or `phase` fields. Find what
   defines the states — a TS union/enum, Python `Enum`, Go `const`/`iota` block,
   or a Rust `enum` (often the states *are* the type). Find the transitions
   (methods that change status, functions returning a new state, or a state-machine def).

3. **Relationships**: look at foreign keys and association methods if there's a
   DB; otherwise at how types reference each other directly — a struct field
   holding another type, an `enum` variant carrying a payload, a slice/`Vec` of
   children, an ID reference resolved in code. Note cardinality (one-to-many,
   many-to-many) and whether the relationship is mandatory or optional.

4. **Key business attributes**: not every field — just the ones that drive
   business decisions. Skip `created_at`, `updated_at`, metadata fields.

---

## Finding Business Rules & Invariants

Business rules are constraints the system enforces. Where they live depends on
the stack; check whichever of these the repo has:

**Validation schemas / declarations** (most explicit when present):
- Zod / Yup / Joi: `z.string().email().max(255)` tells you the rule
- class-validator decorators: `@IsEmail()`, `@Min(0)`, `@IsNotEmpty()`
- Pydantic validators: `@validator('amount')` with logic
- Rails validations: `validates :email, uniqueness: true`
- **Go**: struct tags (`validate:"required,email"`) if a validator is used —
  otherwise hand-written checks (see guard clauses below); Go often has no schema layer.
- **Rust**: `serde` attributes plus the `validator` crate, or — idiomatically —
  rules encoded in the type system: a constructor returning `Result`, a newtype
  that can only hold valid values, an `enum` that makes invalid states
  unrepresentable. "The type enforces it" is a real, common answer.

**Service / use-case pre-conditions** (illustrative; same idea returns an error
in Go/Rust rather than throwing):
```typescript
if (order.status !== 'draft') throw new InvalidStateError(...)
```
```go
if order.Status != Draft { return ErrInvalidState }
```

**Database constraints** (in migrations) — only if there's a DB:
- `UNIQUE` → uniqueness invariants
- `CHECK` → value invariants
- `NOT NULL` + `FOREIGN KEY` → required relationships

**Guard clauses at the top of functions/methods**:
Early returns, thrown errors, or returned `error`/`Err(..)` before the main logic
— usually invariant checks. In Go and much Rust this is the *primary* place rules
live, not a schema.

---

## Tracing Operations / Use Cases

For each major operation:

1. **Find the entry point**: a route handler, CLI command/subcommand, event
   handler, scheduled job, or — for a library — an exported function. Use the
   shape from the survey: a CLI's operations are its commands; a library's are
   its public API.

2. **Follow the call chain** down to where data is persisted, an event is emitted,
   a file is written, or a value is returned. The interesting logic usually lives
   in a service/use-case layer if one exists; in flatter Go/Rust/functional code
   it lives in the function the entry point calls directly.

3. **Note the transaction boundary** if there's a DB: where does `BEGIN`/`COMMIT`
   (or `db.Transaction(..)`, a transaction closure) happen? This tells you what
   must succeed atomically. If there's no DB, note the equivalent atomic unit if
   any (a file written then renamed, a single API call) — or state there is none.

4. **Find side effects**: what else happens beyond the main state change?
   - Emails sent
   - Events published
   - Webhooks triggered
   - Cache invalidated
   - Other services called

5. **Find the error cases**: what can go wrong? Error types thrown tell you
   the business rules being enforced.

---

## Mapping Workflows (Multi-Step Processes)

Some operations are actually multi-step workflows. Signs:
- A `status` field with 4+ states
- A `WorkflowService` or `ProcessManager` or `Saga`
- Multiple operations that must happen in sequence
- Compensating actions (rollback logic)

For workflows, trace: what triggers each transition? What happens at each step?
Who/what is responsible for moving to the next step?

---

## Reading Seed Data / Fixtures

Seed data reveals what real domain objects look like. Very useful for:
- Understanding realistic attribute values
- Seeing which relationships are typically populated
- Understanding the "default" state of the system

Read whatever the repo has: `db/seeds.rb`, `prisma/seed.ts`, `fixtures/*.json`,
`factories/*.py`, Go `testdata/` fixtures or table-test cases, Rust `tests/` fixtures
or `const`/`fn`-built sample values. Often there is none (especially in a no-DB
library) — skip the section rather than inventing data.

---

## Using Tests as Specifications

Integration and acceptance tests often describe behavior better than code.

Look for the behavior named in whatever test idiom the repo uses:
- `describe('when user has insufficient funds')` → domain rule
- `it('should transition order to approved state')` → workflow step
- `expect(invoice.total).toBe(subtotal + tax)` → computed value rule
- **Go**: the `name` field of table-driven test cases and `t.Run("insufficient funds", ...)`
  subtest names; the assertion is the rule.
- **Rust**: `#[test] fn rejects_negative_amount()` names and the asserted condition;
  doctests in `///` comments also encode expected behavior.
- **Python**: pytest function names and `@pytest.mark.parametrize` ids.

Read test names/descriptions (not just assertions) — they're often the clearest
statement of expected behavior in the whole codebase.

---

## Building the Domain Glossary

Every domain has jargon. Find terms that are:
- Used frequently in code but wouldn't be obvious to an outsider
- The same word that means different things in different contexts
- Domain-specific meanings that differ from everyday English

Examples:
- In e-commerce: `Order` vs `Cart` vs `Invoice` vs `Transaction`
- In SaaS: `Workspace` vs `Organization` vs `Account` vs `Tenant`
- In fintech: `Settlement` vs `Transfer` vs `Payment` vs `Transaction`

Note: glossary entries should describe the term **as used in this codebase**,
not its general dictionary definition.
