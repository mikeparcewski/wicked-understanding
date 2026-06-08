---
name: repo-surveyor
description: >
  Perform a fast, structured survey of any code repository to understand its technology stack, file structure, entry points, dependencies, and key files. Use whenever someone asks to understand, explore, or get oriented in a codebase — even casually. Always the mandatory first step before any lens skill or repo-analyst. Triggers on any repo path, GitHub URL, or uploaded archive regardless of language or framework. Run this even if you think you already know the stack — the survey feeds all downstream skills.
---

# repo-surveyor

Produces `survey.md` + `survey.manifest.json` in the per-repo artifacts
directory. Target: under 3 minutes on any repo.

---

## Step 0 — Locate the repo

- Local path: proceed directly.
- GitHub URL: `git clone --depth=1 {url} /tmp/{repo-name}`
- Archive: extract to `/tmp/`

Set `REPO_ROOT` and `REPO_NAME` (basename of root dir).

---

## Step 1 — Read documentation

Skim (30–60 lines each):
- `README.md` / `README.rst`
- `CONTRIBUTING.md`
- `ARCHITECTURE.md` / `DESIGN.md` / `docs/*.md` (top-level only)
- `ADR/` or `docs/adr/` if present

Extract: purpose, target user, stated architectural goals or constraints.

---

## Step 2 — Scan file tree

```bash
# File counts by extension (stack fingerprint)
find "$REPO_ROOT" -type f \
  -not -path '*/.git/*' -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' -not -path '*/vendor/*' \
  -not -path '*/dist/*' -not -path '*/build/*' \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20

# Directory overview (3 levels)
find "$REPO_ROOT" -maxdepth 3 -type d \
  -not -path '*/.git*' -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*'
```

---

## Step 3 — Detect technology stack

**Signature files → stack signals:**

| File | Read fields |
|---|---|
| `package.json` | `main`, `scripts`, `dependencies`, `workspaces` |
| `pyproject.toml` / `requirements.txt` / `setup.py` | deps, entry points |
| `go.mod` | module name, Go version, deps |
| `Cargo.toml` | crate type, deps |
| `pom.xml` / `build.gradle` / `*.csproj` | deps, plugins |
| `Gemfile` / `mix.exs` / `composer.json` / `pubspec.yaml` | deps |

**Infrastructure signals:**
- `Dockerfile` / `docker-compose.yml` → containerized
- `.github/workflows/` / `.circleci/` / `Jenkinsfile` → CI/CD
- `terraform/` / `*.tf` → IaC; `k8s/` / `helm/` → Kubernetes

---

## Step 4 — Find entry points

Adapt to detected stack:
- **Node/TS**: `src/index.*`, `src/main.*`, `src/server.*`, `bin/`
- **Python**: `main.py`, `app.py`, `wsgi.py`, `asgi.py`, `__main__.py`
- **Go**: `main.go`, `cmd/{name}/main.go`
- **Rust**: `src/main.rs`, `src/lib.rs`
- **Java/.NET**: `Program.cs`, `Startup.cs`, `Application.java`

Read 30–50 lines of each entry point to understand initialization.

---

## Step 5 — Scan dependencies & tests

From the manifest file, list top 15 runtime deps with inferred purpose + key dev tools.

```bash
find "$REPO_ROOT" -type f \( -name "*.test.*" -o -name "*.spec.*" \) | head -20
find "$REPO_ROOT" -type d \( -name "test*" -o -name "spec*" \) | head -10
```

---

## Output

**Artifacts directory**: `~/.wicked-understanding/repos/{repo-key}/` — determined by
store keying, which is owned by repo-analyst's `init_understanding.py`. Scripts
ship in their skill's `scripts/` directory — invoke them by the path to the
installed skill (no `$CLAUDE_PLUGIN_ROOT`).

Use the `ARTIFACTS_DIR` that repo-analyst passes when it orchestrates you; if run
standalone, repo-analyst installs alongside this skill — invoke
`python3 ../repo-analyst/scripts/init_understanding.py init --repo-root "$REPO_ROOT"`
(path relative to this skill's directory):

```bash
ARTIFACTS_DIR=$(python3 ../repo-analyst/scripts/init_understanding.py \
  init --repo-root "$REPO_ROOT")
```

Run this first; it prints the artifacts directory to use for all output paths
below. Files use bare names (the directory is already per-repo).

## Output files

### `survey.md`

```markdown
# Survey: {repo-name}

> {one-sentence purpose}

**Generated**: {ISO datetime}  |  **Repo**: {REPO_ROOT}

## At a Glance
| | |
|---|---|
| Primary language | {lang} |
| Framework | {framework(s)} |
| Type | Web API / CLI / Library / Frontend / Monorepo / ... |
| Size | ~{N} files, ~{N}k LOC |
| Test framework | {name} |
| Infrastructure | Docker / K8s / Serverless / None |

## Purpose & Context
{2–3 sentences}

## Repository Structure
{annotated 2-level tree with one-line descriptions per directory}

## Technology Stack
### Runtime Dependencies (top 15)
| Package | Version | Purpose |

### Dev & Build Tools
| Tool | Purpose |

## Entry Points
| Entry point | File | Purpose |

## Key Files
| File | Purpose |

## Build & Run
{install / dev / build / test commands}

## Notable Observations
{3–5 bullets — anything important for downstream lens analysis}
```

### `survey.manifest.json`

```json
{
  "lens": "survey",
  "repo_root": "<REPO_ROOT>",
  "repo_name": "<REPO_NAME>",
  "generated_at": "<ISO datetime>",
  "git_commit": "<git -C $REPO_ROOT rev-parse HEAD 2>/dev/null or null>",
  "watch_patterns": ["**/*"],
  "files_analyzed": [
    { "path": "<relative path from repo root>", "mtime": 0.0, "size_bytes": 0 }
  ]
}
```

Populate `files_analyzed` with every file you actually read.
Get mtime via: `python3 -c "import os; print(os.path.getmtime('<path>'))"`.

---

## After completing

Tell the user the stack/type found, highlight notable observations,
and suggest running `repo-analyst` (or individual lens skills) next.
