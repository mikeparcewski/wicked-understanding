---
name: repo-ops-analyst
description: >
  Analyze the operational setup of a code repository — how to install, run, build, test, debug, and deploy it. Run independently when someone needs to set up the project, understand the CI/CD pipeline, work with environment configuration, or debug operational issues. Requires a survey; run repo-surveyor first if needed. Writes `ops.md` and a manifest sidecar. Trigger on phrases like "how do I run this", "how do I set it up", "what are the environment variables", "how does deployment work", "how do I run tests".
---

# repo-ops-analyst

**Watches**: Dockerfile, docker-compose, CI/CD configs, Makefile/Taskfile,
.env.example, deployment configs, package.json scripts, migration files.

**Outputs**: `ops.md` + `ops.manifest.json`

---

## Prerequisites

Load `survey.md` from the artifacts directory. If it doesn't exist, run `repo-surveyor` first.

---

## Analysis process

Read `references/ops-guide.md` for detailed strategies.

**Priority reading order:**
1. `Makefile` / `Taskfile.yml` / `scripts/` — all runnable operations
2. `package.json` `scripts` field (or equivalent) — all dev commands
3. `.env.example` — all environment variables
4. `Dockerfile` + `docker-compose.yml` — service topology
5. CI/CD config (`.github/workflows/`, `.circleci/`, `Jenkinsfile`)
6. Database migration directory (structure + how to run)
7. Deployment configs (`k8s/`, `helm/`, `terraform/`, `serverless.yml`)
8. `README.md` setup sections (already read — revisit for commands)

---

## Output

**Artifacts directory**: `~/.wicked-understanding/repos/{repo-key}/` — get it via
`init_understanding.py path --repo-root "$REPO_ROOT"` (see repo-surveyor for the
full invocation). Files use bare names.

## Output files: `ops.md`

```markdown
# Operational Guide: {repo-name}

**Generated**: {ISO datetime}

## Prerequisites

| Tool | Version | Purpose | Install |
|---|---|---|---|
| {e.g. Node.js} | >=18 | Runtime | `nvm install 18` |
| {e.g. Docker} | any | Local services | docker.com |
| {e.g. PostgreSQL} | 14+ | Database | via Docker |

## First-Time Setup

```bash
# 1. Clone & install dependencies
git clone {url}
cd {repo-name}
{install command}

# 2. Configure environment
cp .env.example .env
# Required values to set (see Environment Variables section):
#   {VAR1} — {one-line description}
#   {VAR2} — {one-line description}

# 3. Start dependent services (if Docker Compose)
{docker-compose up command}

# 4. Set up the database
{migration command}
{seed command — if applicable}

# 5. Start dev server
{dev command}
# Server available at: {URL}
```

## Daily Development Commands

| Command | What it does |
|---|---|
| `{command}` | Dev server with hot reload |
| `{command}` | Run all tests |
| `{command}` | Unit tests only |
| `{command}` | Integration tests |
| `{command}` | E2E tests |
| `{command}` | Lint + format check |
| `{command}` | Lint + autofix |
| `{command}` | Build for production |
| `{command}` | Type check (if typed) |
| `{command}` | Run pending DB migrations |
| `{command}` | Create new migration |
| `{command}` | Reset DB + re-seed |

## Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `{VAR}` | Yes/No | `{default}` | {what it controls} |

Group by category if many: database, auth, external services, feature flags.

## Service Topology (if Docker)

```yaml
# Services started by docker-compose up:
{service-name}:   {image} — {purpose} — port {N}
{service-name}:   {image} — {purpose} — port {N}
```

## CI/CD Pipeline

- **Platform**: GitHub Actions / CircleCI / Jenkins / GitLab CI
- **Config**: `{path}`
- **Triggers**: push to `{branch}` / PR / tag `v*`
- **Pipeline steps**: lint → unit tests → integration tests → build → deploy
- **Environments**: staging (auto on merge) / production (manual approval)
- **Secrets management**: {how secrets are stored and injected}

## Database

- **Engine**: {PostgreSQL / MySQL / MongoDB / SQLite / etc.}
- **ORM / driver**: `{name}`
- **Migrations location**: `{path}`
- **Run migrations**: `{command}`
- **Rollback**: `{command}` (or: *no rollback command — manual SQL required*)
- **Reset + seed**: `{command}`
- **Schema file**: `{path or none}`

## Debugging & Observability

- **Debug logging**: set `LOG_LEVEL=debug` (or `DEBUG=*`)
- **Log format**: structured JSON / plain text
- **Health endpoint**: `GET {url}/health`
- **Admin UI**: `{url}` or *none*
- **Metrics**: `{Prometheus endpoint / Datadog / none}`
- **Trace sampling**: `{how to enable distributed tracing}`

## Deployment

{Describe the deployment mechanism — enough to understand what a deploy does}

**Trigger**: `{git tag / manual / CI on merge}`
**Mechanism**: `{container push / serverless deploy / k8s apply / etc.}`
**Rollback**: `{how to roll back a bad deploy}`

## Common Issues & Fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `{error message or symptom}` | {cause} | {fix or `{command}`} |
```

---

## Output: `ops.manifest.json`

```json
{
  "lens": "ops",
  "repo_root": "<absolute path>",
  "repo_name": "<name>",
  "generated_at": "<ISO datetime>",
  "git_commit": "<SHA or null>",
  "watch_patterns": [
    "Dockerfile", "Dockerfile.*", "docker-compose*.yml",
    ".github/workflows/**", ".circleci/config.yml", "Jenkinsfile", ".gitlab-ci.yml",
    "Makefile", "Taskfile.yml", "scripts/**",
    ".env.example", ".env.sample",
    "package.json",
    "k8s/**", "helm/**", "terraform/**", "serverless.yml", "sam.yml",
    "migrations/**", "db/migrate/**"
  ],
  "files_analyzed": [
    { "path": "<relative path>", "mtime": 0.0, "size_bytes": 0 }
  ]
}
```
