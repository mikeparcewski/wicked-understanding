---
name: repo-orient
description: >
  Generate or refresh the always-in-context agent context doc
  (CLAUDE.md / AGENTS.md / GEMINI.md) for an analyzed repo, distilled from the
  lens artifacts and routing agents to the generated task skills + wiki. This is
  the cheapest always-loaded surface: it orients every session in a few dozen
  lines and points at the curated skills instead of re-exploring the codebase.
  Merge-safe — augments a managed block, never clobbers hand-written rules.
  Trigger on "generate the context doc", "write the CLAUDE.md", "create
  AGENTS.md from the analysis", "orient agents to this repo", or after the
  skills + wiki are generated.
---

# repo-orient

Writes the one file every agent reads first. The generated task skills and wiki
load *on demand*; this doc is *always* in context, so its job is to **orient in
a few dozen lines and route to those skills** — never to duplicate them. This is
where the token savings compound: a ~50-line block replaces re-reading the repo
to get oriented, every session.

It is the only output that lives in the analyzed repo's tree (CLAUDE.md /
AGENTS.md / GEMINI.md). The skills install CLI-side via `npx skills`; this doc is
repo-resident because that's where agents read it.

---

## Input

```bash
ARTIFACTS_DIR=$(python3 ../repo-analyst/scripts/init_understanding.py \
  path --repo-root "$REPO_ROOT")
```
(Use the `ARTIFACTS_DIR` repo-analyst passes when it orchestrates you; standalone,
repo-analyst installs alongside this skill. Scripts are bundled per-skill — no
`$CLAUDE_PLUGIN_ROOT`.)

Read from `$ARTIFACTS_DIR`: `survey.md`, `architecture.md`, `domain.md`,
`technical.md`, `ops.md`. Then read the generated package at
`$ARTIFACTS_DIR/skills/` to learn the real `{repo-slug}-*` skill names and the
`{repo-slug}-wiki/refs/*` filenames — you must route to names that exist.

If artifacts are missing, run `repo-analyst` first.

---

## What to write (the managed block — keep it TIGHT)

This block is always in context; every line costs every session. **Target ≤ ~80
lines.** Depth lives in the skills/wiki you route to — do not restate them.

Author the block body (no markers — the script adds them) with:

1. **One-liner + how to run** — from survey + ops. What it is, stack/type, and
   the 3–5 commands an agent needs (install / dev / test). Real commands only.
2. **Locked decisions · conventions · gotchas · repo-specific don'ts** — from
   architecture / domain / technical. Only the non-obvious, high-value items
   (the things that cause bugs or that an agent would get wrong). No generic
   advice. Every line must read false if you swapped in another repo's name.
3. **Routing table (the payoff)** — map intents to the generated skills + wiki
   refs, using their REAL names:

   ```markdown
   | When you're… | Load |
   |---|---|
   | Fixing a bug | `{repo-slug}-fix-bug` |
   | Adding a feature | `{repo-slug}-add-feature` |
   | Verifying a change / is it done? | `{repo-slug}-verify` |
   | Understanding the architecture | `{repo-slug}-wiki` → `refs/arch.md` |
   | Understanding the domain | `{repo-slug}-wiki` → `refs/domain.md` |
   ```
   Include only rows for skills/refs that were actually generated (check
   `$ARTIFACTS_DIR/skills/`). End with one line: "Prefer these over re-reading
   the codebase — they're curated and cited."

**Note — don't restate the human section.** The lens artifacts may have absorbed
content from the repo's EXISTING CLAUDE.md, so a fact can land both in the
human-authored section (outside the markers) and your managed block. That's
harmless, but SYNTHESIZE and ROUTE rather than restate verbatim what already sits
in the human section — the managed block earns its always-in-context space by
pointing to the skills/wiki, not by duplicating existing prose.

---

## How to write it (merge-safe — never clobber)

1. Write the block body to a temp file, e.g. `/tmp/{repo}-orient.md` (body only).
2. Write the SAME managed block into BOTH `CLAUDE.md` AND `AGENTS.md` — run the
   bundled merge script once per target (relative to this skill's directory).
   Add `GEMINI.md` as a third target if the repo uses Gemini.

   ```bash
   python3 scripts/merge_context_doc.py \
     --target "$REPO_ROOT/CLAUDE.md" \
     --content-file /tmp/{repo}-orient.md \
     --verify-routes "$ARTIFACTS_DIR/skills"

   python3 scripts/merge_context_doc.py \
     --target "$REPO_ROOT/AGENTS.md" \
     --content-file /tmp/{repo}-orient.md \
     --verify-routes "$ARTIFACTS_DIR/skills"
   ```

   `--verify-routes <package-dir>` fails if a routing-table row points at a
   skill/ref absent from the generated package — dead links are a hard failure,
   not an inspection step.

   If the analyzed repo already mirrors `CLAUDE.md` and `AGENTS.md` via a
   symlink, merge into the real file once — the symlink reflects it. Mirror
   whatever the repo already does.

3. The script inserts or refreshes ONLY the text between
   `<!-- wicked-understanding:context:start -->` and `:end`. Everything the human
   wrote outside the markers is preserved byte-for-byte. Re-running refreshes the
   block in place — safe to run on every analysis refresh.

---

## Quality bar

- [ ] Block ≤ ~80 lines — it's the always-in-context tax; trim hard.
- [ ] Every routing-table row points to a skill/ref that exists in `$ARTIFACTS_DIR/skills/`.
- [ ] Ran with `--verify-routes "$ARTIFACTS_DIR/skills"` — the merge exited 0, so no row points at a missing skill/ref.
- [ ] Every decision / gotcha / don't is repo-specific (no name-swappable filler).
- [ ] Commands are real and copy-pasteable (from ops.md).
- [ ] You wrote only the body; the script owns the markers. Never write outside the block.
- [ ] If a lens is thin, say less — don't pad an always-loaded file.

---

## After

Report which context files got the block and confirm hand-written content was
preserved (the merge script prints `created` / `replaced` / `appended` per file).
Tell the user the doc routes agents to the generated skills, so the next session
starts oriented for ~50 lines instead of re-exploring the repo.
