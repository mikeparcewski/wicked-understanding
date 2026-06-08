# Tests

Stdlib-only (`unittest`) tests for the four deterministic scripts. Each test
invokes the **real script entry point as a subprocess** (`sys.executable
script.py ...`) — no internals are reached except one importlib check of
`normalize_remote_url`. Tests are hermetic: anything that touches
`~/.wicked-understanding` runs with `HOME`/`USERPROFILE` pinned to a tempdir.

## Run

From the plugin root:

```bash
python3 -m unittest discover -s tests -v
```

## Layout

| File | Script under test |
|---|---|
| `test_init_understanding.py` | `repo-analyst/scripts/init_understanding.py` |
| `test_check_freshness.py` | `repo-analyst/scripts/check_freshness.py` |
| `test_assemble_wiki_skill.py` | `repo-wiki-planner/scripts/assemble_wiki_skill.py` |
| `test_generate_viewer.py` | `repo-wiki-planner/scripts/generate_viewer.py` |
| `_support.py` | shared helpers (script paths, subprocess runner, hermetic env) |
| `fixtures/` | input artifacts, a wiki plan, and a sample wiki skill dir |

The `freshness` and `assembler` tests run in OS-temp dirs that are not inside any
git repo, which exercises `check_freshness`'s mtime-fallback path. The assembler
fixture's `domain.md` uses the real repo-domain-analyst "Core Entities" format
(`### Name` H3 blocks + `- **Represents**: ...` bullets); its plan deliberately
uses `mcp-tools.md` (not `api.md`) for the api-reference to guard against
hardcoded ref links.

`git` is required for the remote-URL-normalization end-to-end case in
`test_init_understanding.py`; that single test skips cleanly if `git` is absent.
