# Ops Analysis Guide

Reference for `repo-ops-analyst`. Read before starting analysis.

---

## Detect the stack first (the files below are illustrative)

The config files, commands, and examples in this guide span ecosystems (and lean on
Node/Docker/migration-based web services where unmarked). They are a menu, not a
checklist. Before applying any of them, fix from the survey:

- **Language(s) and build tool** — this is the anchor: `package.json`+npm/pnpm,
  `Makefile`, `go build`/`go.mod`, `cargo`/`Cargo.toml`, Maven/Gradle, `pyproject.toml`.
  The "runnable commands" live wherever this repo defines them.
- **Shape** — service vs CLI vs library vs batch. A library or CLI usually has *no*
  Dockerfile, *no* compose topology, *no* deploy manifests, and *no* DB/migrations.
- **Persistence** — has-DB vs no-DB. No DB means no migrations section.
- **Distribution** — long-running deploy (k8s/serverless) vs a built binary/published
  artifact (a Go binary, a `cargo install` crate, an npm package, a release tarball).

Describe what exists. Never assume Docker, a CI pipeline, migrations, env files, or a
cloud deploy the repo does not have. **"No Docker", "no migrations", "no DB", "no
CI", "ships a single static binary" are valid, common, first-class findings** —
report them plainly instead of hunting for absent infrastructure or padding the
section. For a library/CLI the ops story may legitimately be just "build, test,
publish".

---

## Reading Runnable Commands

Find where this repo defines its commands (build tool from the survey), then read
the actual command behind each name — the flags matter.

**Makefile**: Read all targets. Targets prefixed with `##` are usually
self-documented. Map target names to what they do. (Common in Go/Rust/C repos as the
primary task runner.)

**package.json scripts**: Every key in `"scripts"` is a runnable command. Note the
name *and* the underlying `{tool} {flags}` it runs.

**Go**: there's often no script file — commands are `go build ./...`, `go test ./...`,
`go run ./cmd/x`, `go vet`, plus a `Makefile` wrapping them. Note the module path
from `go.mod` and any `//go:generate` directives.

**Rust / Cargo**: `cargo build`/`test`/`run`/`clippy`/`fmt`; check `Cargo.toml`
`[[bin]]`/`[workspace]` for what's built, `[features]` for build variants, and any
`xtask`/`just`/`cargo-make` (`Makefile.toml`) task runner.

**Other task runners**: `Taskfile.yml` (read `tasks:`), `justfile` (read recipes),
`Rakefile`, `tox.ini`/`nox`, Gradle/Maven goals. Read whichever is present.

**scripts/ directory**: List and skim each file. Note which are run directly vs
which are helpers called by others.

---

## Reading Docker Files

Many repos have no Docker at all (libraries, CLIs, many Go/Rust tools that ship a
binary). If there's no `Dockerfile`/`compose`, say so and move to how the artifact is
actually built and run (`go build` → a binary, `cargo build --release` → `target/release/x`,
a published package). Don't treat absent Docker as a gap. When a Dockerfile *is*
present for a compiled language, note whether it's a multi-stage build (build stage
compiles, final stage is a slim/`scratch`/`distroless` runtime with just the binary)
— that's the common Go/Rust pattern.

**Dockerfile:**
- `FROM` — base image and version (pinned? floating?)
- `WORKDIR` — where the app lives
- `COPY` / `ADD` steps — what gets included (and excluded via `.dockerignore`)
- `RUN` steps — build-time operations (install, compile, etc.)
- `ENV` — environment variables baked in
- `EXPOSE` — ports
- `CMD` / `ENTRYPOINT` — how the container starts
- Multi-stage builds — usually means `build` stage + `production` stage

**docker-compose.yml:**
Read to understand the full service topology:
- What services run (`services:` keys)
- What images are used
- How services depend on each other (`depends_on:`)
- Volume mounts (where code/data is persisted)
- Environment variable sources (`env_file:`, `environment:`)
- Port mappings (host:container)
- Which service is the app vs which are supporting services (DB, cache, queue)

---

## Reading Environment Variables

`.env.example` is the authoritative source *when it exists*. Many CLIs/libraries take
config via flags, a config file (`config.toml`/`yaml`), or no env at all — note that
instead of inventing variables. For each variable:

1. **Infer purpose from name**: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`,
   `STRIPE_SECRET_KEY`, `LOG_LEVEL`, `PORT` (`NODE_ENV` is Node-specific; the
   analogue is `GO_ENV`/`RUST_LOG`/`APP_ENV` or none).

2. **Check if there's documentation**: comments in `.env.example`, or a
   `docs/environment.md` file

3. **Find usage in code** — grep the language's accessor, not just Node's:
```bash
grep -rn "process.env" .                      # Node
grep -rn "os.Getenv\|os.LookupEnv" .          # Go
grep -rn "env::var\|std::env" .               # Rust
grep -rn "os.environ\|os.getenv" .            # Python
```

4. **Categorize**:
   - Infrastructure: `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`
   - Authentication: `JWT_SECRET`, `SESSION_SECRET`, `OAUTH_CLIENT_ID`
   - External services: `STRIPE_SECRET_KEY`, `SENDGRID_API_KEY`, `S3_BUCKET`
   - Runtime behavior: `LOG_LEVEL`, `PORT`, `NODE_ENV`, `DEBUG`
   - Feature flags: `ENABLE_*`, `FF_*`

---

## Reading CI/CD Configs

**GitHub Actions** (`.github/workflows/*.yml`):
- `on:` — triggers
- Each `job:` — what runs in parallel
- Each `step:` within a job — what runs in sequence
- `needs:` — job dependencies (defines pipeline DAG)
- `secrets:` / `vars:` — how secrets are injected
- `environment:` — which deployment environment (staging/production)

Also check non-GitHub CI if present: `.gitlab-ci.yml`, `.circleci/config.yml`,
`Jenkinsfile`, Azure Pipelines, `.travis.yml`. If there's no CI config at all, state
that — it's a common and valid finding (and a real gap worth flagging for a service).

**Key questions to answer:**
1. What triggers the pipeline? (push to main? PR? tag?)
2. What runs in CI? Name the actual steps for this stack — e.g. `npm test`/`eslint`;
   `go build ./... && go test ./... && go vet ./...` + `golangci-lint`;
   `cargo build && cargo test && cargo clippy && cargo fmt --check`; `pytest`/`ruff`/`mypy`.
3. Is deployment automatic or manual? (For a library/CLI, "deploy" is often a
   publish/release on tag — `cargo publish`, `npm publish`, `goreleaser`, a GitHub
   Release with built binaries — not a server rollout.)
4. What are the deployment environments? (May be none.)
5. How are secrets managed?

---

## Reading Deployment Configs

**Kubernetes / Helm:**
Look for `kind: Deployment`, `kind: Service`, `kind: Ingress` in YAML files.
Note: replicas, image pull policy, resource limits, health check paths,
environment variable injection from ConfigMaps/Secrets.

**Terraform:**
Look for `resource "aws_*"` / `resource "google_*"` blocks.
Note what cloud resources are provisioned.

**Serverless:**
`functions:` in `serverless.yml` — each function is a deployable unit.
Note: runtime, memory, timeout, triggers (HTTP, schedule, event).

---

## Documenting Database Operations

**Only if the repo has a database.** Confirm from the survey first — no DB means no
migrations, and "this project has no database / persists to files / is stateless" is
the complete and correct answer for this section. Don't hunt for a migration tool
that isn't there.

If there is a DB, find and document:
1. **How to run migrations**: the command that applies pending migrations
2. **How to create a migration**: the command that generates a new migration file
3. **How to check status**: which migrations are applied?
4. **How to reset**: drop + recreate + re-run all migrations
5. **Where migrations live**: relative path
6. **Migration tool**: Flyway, Alembic (Python), Rails migrations, Prisma/Knex/
   TypeORM (Node), `golang-migrate`/`goose`/`atlas`/GORM AutoMigrate (Go),
   `sqlx migrate`/`diesel`/`sea-orm` (Rust) — name the one actually in use, or note
   raw SQL files applied by hand.

---

## Building the "Common Issues" Table

Look for clues in:
- `TROUBLESHOOTING.md` or `FAQ.md` if they exist
- GitHub issues (if accessible)
- Comments in setup scripts that say `# This often fails because...`
- README warnings or notes sections

If none of these exist, infer common issues from *this repo's* setup complexity —
only list ones that apply:
- If many env vars required → "forgot to set env var X"
- If Docker required → "Docker not running"
- If a specific runtime/toolchain version is pinned → "wrong version" (Node via
  `.nvmrc`/`engines`; Go via `go.mod` `go 1.xx`; Rust via `rust-toolchain.toml`/
  edition; Python via `.python-version`)
- If migrations needed → "forgot to run migrations after pull"
- Compiled langs: missing system libs / CGO toolchain (Go), missing C deps or wrong
  target for `cargo build` (Rust), `GOFLAGS`/proxy issues fetching modules
- If it ships a binary → "stale build, re-run `make`/`go build`/`cargo build`"
