# Technical Analysis Guide

Reference for `repo-tech-analyst`. Read before starting analysis.

---

## Detect the stack first (the patterns below are illustrative)

The conventions, signals, and examples in this guide span ecosystems (and lean on
TS/REST/OO where unmarked). They are a menu, not a checklist. Before applying any
of them, fix what this repo actually is — from the survey:

- **Language(s)** and the idiomatic unit (class, module, package, crate, function).
- **Paradigm**: OO vs functional vs procedural. Error handling, data transformation,
  and "patterns" all look different in `Result`-returning Go/Rust or a functional
  Python core than in exception-throwing OO TS/Java.
- **Shape**: web service vs CLI vs library vs batch/job. "API surface" means HTTP
  routes for a service, the command tree for a CLI, the public exports for a library.
- **Persistence**: has-DB vs no-DB. No DB means no repository pattern, no DTO↔row
  mapping — don't hunt for them.
- **Build/lint tooling**: anchors the quality-gate and convention story.

Describe what exists. Never assume exceptions, a DI container, an ORM, a serializer
layer, or a REST surface the repo does not have. If a section's signals don't
appear, say so plainly — absence is data.

---

## Sampling Source Files

Don't read everything. Pick a representative sample, mapped to this repo's shape:
- 1–2 files per layer/grouping *that exists* — handler/service/repository/model in a
  layered service; in flat Go/Rust/functional code, sample by package/module/crate
  (`cmd/`, `internal/*`, workspace members) instead, since there may be no layers.
- 1 complex file (longest or most-imported)
- 1 recently modified file (from `git log --oneline -20`)
- 1 test file (co-located with an important module; Go `*_test.go`, Rust `#[cfg(test)]`
  modules or `tests/`, pytest files)

From this sample you should be able to infer the patterns used across the
whole codebase. If you see contradictions (different patterns in different
files), note the inconsistency.

---

## Identifying Naming Conventions

Read 10–15 file and function names and look for consistency.

**File naming**: kebab-case (`user-service.ts`), snake_case (`user_service.py`,
Rust modules), PascalCase (`UserService.java`), or mixed? Go convention is short
lowercase package dirs with `snake_case.go` files; note if the repo follows it.

**Function naming**: Note the verb choices. Do operations start with `get`/`find`/`fetch`
(query side) vs `create`/`update`/`delete` vs `handle`/`process`? This tells
you the naming taxonomy. By stack: Go exports by capitalization (`GetUser` is
public, `getUser` is package-private) — note that convention rather than a suffix
scheme; Rust uses `snake_case` fns and a `new`/`with_*`/`try_*` constructor idiom.

**Type / interface naming**: note suffixes/conventions actually in use. TS often
has `Dto`/`Input`/`Response`/`Payload`/`Model`/`Entity`; Go interfaces often take an
`-er` suffix (`Reader`, `Store`); Rust traits are often capability-named
(`Serialize`, `Display`) and newtypes wrap primitives. Record what the suffixes
mean *in this codebase*, or note that the language leans on plain names.

---

## Reading Error Handling

Error handling is one of the most important things to document because
it's often implicit and inconsistent. **Identify the model first** — it is
language-shaped, and getting it wrong distorts the whole section:

- **Exceptions (TS/Java/Python/Ruby)**: errors are thrown and caught; there's
  usually a class hierarchy and a central handler. Sections below assume this.
- **Returned values — Go**: functions return `(T, error)`; the idiom is
  `if err != nil { return ..., fmt.Errorf("...: %w", err) }` (wrap), and
  `errors.Is`/`errors.As` at the boundary. There is no throw. Sentinel errors
  (`var ErrNotFound = errors.New(...)`) and custom error types are the "hierarchy".
- **Returned values — Rust**: `Result<T, E>` with the `?` operator propagating;
  a crate-wide error `enum` (often via `thiserror`) is the hierarchy, `anyhow` at
  the top. `panic!`/`unwrap` is the non-recoverable path — note where it's used.
- **Functional**: `Either`/`Result`/`Option` monads, railway-oriented flow; errors
  are values threaded through `map`/`and_then`, not thrown.

**Find the error type set:**
```bash
# exception hierarchies
grep -rn "extends Error\|class.*Error\|AppError\|BaseError" --include="*.ts" .
grep -rn "class.*Exception\|BaseException" --include="*.py" .
# Go sentinel + custom errors
grep -rn "errors.New\|fmt.Errorf\|func.*Error() string" --include="*.go" .
# Rust error enums / propagation
grep -rn "thiserror\|enum.*Error\|impl.*Error\|-> Result<" --include="*.rs" .
```

**Trace what happens to an error** (translate "throw/catch" to "return/check" for
Go/Rust): where it originates, whether an intermediate layer wraps/maps it to a
different type, what handles it at the boundary, and how it becomes the final
output — an HTTP response for a service, an exit code + stderr for a CLI, or a
returned `Err`/`Result` for a library.

**Look for the central handling point:**
- Express: `app.use((err, req, res, next) => ...)`; NestJS: `@Catch()` filter;
  FastAPI: `@app.exception_handler()`; Rails: `rescue_from`.
- Go: error-handling middleware, or a single point in `main`/the handler that maps
  `error` → response/exit code; often there is no global handler by design.
- Rust: a `From`/`?`-based conversion into one error type plus an `IntoResponse`
  impl (axum) or a `match` in `main` returning an exit code.
- CLI (any language): where a returned/caught error is turned into a message +
  non-zero exit.

---

## Understanding Data Transformation

The inbound/outbound framing below is web-service-shaped. Generalize "request" to
*whatever crosses the boundary*: a CLI's args/flags + stdin, a library's function
arguments, a job's input file/message. Skip this section if data barely transforms
(e.g. a tool that operates on one in-memory type end to end) — say so.

**Input → domain (inbound):**
Find where raw input gets parsed and validated. A JSON body through a DTO/Zod
schema/serializer (web); a Go struct decoded via `encoding/json` + struct tags, or
flags parsed by cobra/`flag`; Rust `serde` deserialization into a typed struct, or
clap into an args struct; argparse/click for Python CLIs. Is validation separate
from transformation, or combined (e.g. parse-don't-validate into a type that can
only hold valid values)?

**Domain → output (outbound):**
How do domain objects become the result?
- Explicit serializer / presenter (`UserSerializer`, `UserPresenter`); `.toJSON()`.
- Auto-serialization (all fields exposed) vs manual mapping in the handler.
- Go: `json.Marshal` with struct tags (`json:"...,omitempty"`, `json:"-"` to hide).
- Rust: `serde::Serialize` derive with `#[serde(skip)]`/`rename`.
- CLI/library: formatted text/tables to stdout, or a returned value — there may be
  no serialization at all.

**Key question**: are there fields intentionally excluded from output (passwords,
internal flags)? Find where that exclusion happens — a presenter, `json:"-"`,
`#[serde(skip)]`, or a `select` that omits the column.

---

## Recognizing Design Patterns

These are GoF/OO patterns; report the ones that are actually present. In functional
or procedural code the same intent shows up differently (a higher-order function
instead of a Strategy object, a closure instead of a Decorator) — describe the
mechanism the repo uses, and don't manufacture a pattern that isn't there.

**Repository pattern:**
A type with `findById()`/`findAll()`/`save()`/`delete()`, usually one per entity.
TS/Java interface or class; Go a `Store`/`Repository` `interface` with a DB-backed
impl; Rust a `trait` plus an impl. Check if it's an abstraction (testable) or
concrete. Often absent in no-DB tools — that's fine to report.

**Factory / Builder:**
`UserFactory.create(overrides)` or `new OrderBuilder().withItems(...)`. Go/Rust
idiom: `New*`/`new`/`with_*` constructor functions and functional-options
(`func(*Config)`) or a builder struct. Often used in test fixtures.

**Decorator / Middleware / wrapping:**
`@UseGuards(AuthGuard)`, `@Transactional()`, `@Cached(ttl=300)` annotate behavior
without changing the body. Go has no decorators — the equivalent is
`func(http.Handler) http.Handler` middleware or a wrapping function; Rust uses tower
`Layer`s, attribute macros, or wrapper types. List whichever the repo uses.

**Observer / Event:**
`eventBus.publish(new OrderCreated(order))` + `@EventHandler(...)`; or Go channels +
goroutines / a callback registry; Rust channels (`mpsc`) or an event enum matched by
a loop. Find both emitters and handlers.

**Strategy:**
Interchangeable implementations selected at runtime — `PaymentProvider` →
`StripeProvider`/`PaypalProvider`. Go: a set of types implementing one `interface`;
Rust: `Box<dyn Trait>`/generics; functional: a function value chosen and passed in.

---

## Documenting "How to Add X"

This is the most practically valuable section. Be specific, and pick an "X" that
fits the shape: add an endpoint (service), add a subcommand (CLI), add a public
function/trait impl (library), add a job/handler (batch/event). Trace an *existing*
one of that kind end to end and write the exact steps to replicate it, with the
specific imports, base types, interfaces/traits, registration call, or decorators.

Good step (web/DI example — adapt to the repo):
```
2. Create handler in `src/handlers/` extending `BaseHandler`:
   - Constructor injects service via DI: `constructor(private readonly userService: UserService)`
   - Method decorated with `@Get('/:id')` and `@Roles('admin')`
   - Call service, map result with `UserResponseDto.fromEntity(result)`, return
```

Good step (Go CLI example):
```
2. Add `cmd/sync.go`: define `var syncCmd = &cobra.Command{Use: "sync", RunE: runSync}`,
   register it in `init()` with `rootCmd.AddCommand(syncCmd)`, and put logic in
   `runSync(cmd *cobra.Command, args []string) error` calling the `internal/sync` pkg.
```

Useless step (any stack):
```
2. Create a handler file
```

---

## API Surface Documentation

Document the surface that matches the shape (see "Detect the stack first"). For a
**CLI**, document the command tree: command/subcommand naming, global vs per-command
flags, exit-code convention, stdin/stdout contract. For a **library**, document the
public API: the entry types/traits/functions, what's `pub`/exported vs internal,
and the stability/versioning story. For a service, use the relevant subsection below.

For REST APIs, document the conventions, not every endpoint:
- Resource naming convention (plural nouns? singular?)
- How IDs appear in paths (`/users/:id` vs `/users/:userId`)
- Standard query params (pagination, filtering, sorting)
- Response envelope structure
- Error response structure

For GraphQL, document the schema organization:
- How queries vs mutations are organized
- Resolver co-location strategy
- How N+1 is handled (DataLoader? join strategy?)

For gRPC, note the proto organization and any generated code patterns.
