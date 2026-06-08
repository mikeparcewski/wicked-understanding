---
name: repo-tech-analyst
description: >
  Analyze the technical implementation patterns, coding conventions, APIs, key algorithms, and idioms of a code repository. Run independently when someone needs to understand how code is written (not what it does), review coding patterns, understand the API surface, or onboard to technical conventions. Requires a survey; run repo-surveyor first if needed. Writes `technical.md` and a manifest sidecar. Trigger on phrases like "what are the coding conventions", "how is error handling done", "what patterns are used", "explain the API", "how do I add a new feature".
---

# repo-tech-analyst

**Watches**: source files (broad), error handler modules, test files,
lint/formatter config, type definitions, utility modules, API definitions.

**Outputs**: `technical.md` + `technical.manifest.json`

---

## Prerequisites

Load `survey.md` from the artifacts directory. If it doesn't exist, run `repo-surveyor` first.

---

## Analysis process

Read `references/technical-guide.md` for detailed strategies.

**Priority reading order:**
1. Sample 5–8 representative source files across different layers
2. Error handling / exception modules
3. Utility / helper modules (`utils/`, `lib/`, `common/`, `helpers/`)
4. Middleware or decorator definitions (reveal cross-cutting patterns)
5. Type aliases and branded types
6. A representative test file (reveals testing patterns)
7. Lint / formatter config (`.eslintrc`, `pyproject.toml`, `.golangci.yml`)
8. Code generation templates (if any — define canonical patterns)

---

## Output

**Artifacts directory**: `~/.wicked-understanding/repos/{repo-key}/` — get it via
`init_understanding.py path --repo-root "$REPO_ROOT"` (see repo-surveyor for the
full invocation). Files use bare names.

## Output files: `technical.md`

```markdown
# Technical Reference: {repo-name}

**Generated**: {ISO datetime}

## Conventions

| Aspect | Convention | Example |
|---|---|---|
| File naming | {kebab-case / snake_case / PascalCase} | `user-service.ts` |
| Function naming | {camelCase verbs} | `getUserById()` |
| Class naming | {PascalCase nouns} | `UserRepository` |
| Constants | {SCREAMING_SNAKE} | `MAX_RETRY_COUNT` |
| Types/interfaces | {PascalCase} | `CreateUserInput` |
| Test files | {co-located / separate} | `user.service.test.ts` |
| Comments | {JSDoc / docstrings / inline} | `/** @param {User} */` |

## Error Handling

- **Mechanism**: {exceptions / Result<T,E> / error codes / callbacks}
- **Error class hierarchy**: {describe — e.g., AppError → NotFoundError, ValidationError}
  Defined in: `{file}`
- **API error format**: `{"error": {"code": "...", "message": "..."}}` — `{file}`
- **Propagation**: {how errors travel from domain to transport layer}
- **Async errors**: {how rejections / panics are caught}

## Data Transformation Flow

1. **Input parsing**: {library + where} — `{file}`
2. **Request → domain**: {DTOs? manual mapping? auto-serialization?}
3. **Domain → response**: {serializers? mappers? direct?}
4. **Null/optional handling**: {undefined checks / Option type / null coalescing}

## Async / Concurrency

- **Style**: {async/await / Promises / goroutines / threads / actors}
- **Concurrent operations**: {Promise.all / errgroup / asyncio.gather}
- **Async error handling**: {try/catch in async / Result propagation}

## Patterns in Use

| Pattern | Where applied | Example file |
|---|---|---|
| {Repository} | Data access | `{path}` |
| {Factory / Builder} | Object creation | `{path}` |
| {Decorator / Middleware} | Cross-cutting | `{path}` |
| {Observer / Event} | Side effects | `{path}` |
| {Strategy} | Algorithm variants | `{path}` |

(Include only patterns actually present)

## Adding New Features

**New API endpoint:**
1. {Step 1: where to add route}
2. {Step 2: handler convention — show the pattern}
3. {Step 3: service/use-case}
4. {Step 4: test}

**New domain entity:**
1. {Step 1: create entity file — template/base class}
2. {Step 2: migration command}
3. {Step 3: repository}
4. {Step 4: wire in DI}

## API Surface

(If applicable)
- **Style**: REST / GraphQL / gRPC / tRPC / WebSocket
- **Base path**: `/api/v1` or similar
- **Auth header**: `Authorization: Bearer <token>` or `X-API-Key`
- **Standard response envelope**: `{"data": ..., "meta": ...}` — `{file}`
- **Pagination convention**: cursor / offset — `{how it works}`
- **Error response**: `{"error": {"code": "...", "message": "..."}}` — `{file}`

## Testing Patterns

- **Frameworks**: {Jest + Supertest / pytest / Go testing / etc.}
- **Test types**: unit (`{path}`) / integration (`{path}`) / E2E (`{path}`)
- **Mock/stub approach**: {jest.mock / unittest.mock / testify/mock / etc.}
- **Test data**: {factories in `{path}` / fixtures in `{path}` / inline builders}
- **Commands**: `{unit}` / `{integration}` / `{all}`

## Non-Obvious Technical Details

Things that would trip up a developer:
- **{Observation}**: {explanation} — `{file}`
- **{Observation}**: {explanation}
```

---

## Output: `technical.manifest.json`

```json
{
  "lens": "technical",
  "repo_root": "<absolute path>",
  "repo_name": "<name>",
  "generated_at": "<ISO datetime>",
  "git_commit": "<SHA or null>",
  "watch_patterns": [
    "src/**/*.ts", "src/**/*.py", "src/**/*.go", "src/**/*.rs",
    "src/errors.*", "src/exceptions.*",
    "src/utils/**", "src/lib/**", "src/helpers/**", "src/common/**",
    "src/middleware/**", "src/decorators/**",
    "**/*.test.*", "**/*.spec.*",
    ".eslintrc*", "pyproject.toml", ".golangci.yml", ".rubocop.yml",
    "openapi.yml", "openapi.json", "swagger.*"
  ],
  "files_analyzed": [
    { "path": "<relative path>", "mtime": 0.0, "size_bytes": 0 }
  ]
}
```

Narrow `watch_patterns` to the actual source file extensions in this repo.
