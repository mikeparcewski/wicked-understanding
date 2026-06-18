"""
Functional test for the agent-comprehensiveness gate's DETERMINISTIC backstop.

Context: cross-pollination rec #1 replaced the ">8 articles → confirm with the
user" HUMAN gate in repo-wiki-planner with (A) an agent-judged plan-reviewer
sub-step (LLM — SKILL.md Step 1.5, not testable here) and (B) a deterministic
`--max-articles` runaway ceiling in assemble_wiki_skill.py. This file pins the
deterministic half (B) — the part that is LLM-free and must never regress.

What needs a LIVE MODEL (NOT covered here, by design): the Step 1.5 reviewer's
coverage/redundancy/evidence-warrant judgment and its prose `## See also`
reconciliation inside generated article bodies. Those are agent work. This test
covers the deterministic scaffolding that makes the unattended path safe:

  a) the pipeline PROCEEDS UNATTENDED on a >8-article plan — the script exits 0
     and writes the router with no stdin / no human prompt;
  b) the backstop TRIMS a pathological count down to the cap, dropping only
     capability/concept-explanation articles, lowest-priority-first;
  c) always-on (product-overview, onboarding-maintainer) and ALL structural
     types (architecture-overview, api-reference, domain-reference,
     design-pattern, runbook, agent-roster) are NEVER auto-dropped — every one
     of the 8 non-trimmable types is exercised by the fixture, not just 4;
  d) the trim report enumerates `trimmed_canonical_ids` so the reviewer / the
     `broken_reference` lint can reconcile surviving `## See also` rows — and
     the assembled router's Load guide contains NO link to a trimmed ref
     (no dead intra-wiki link escapes the deterministic layer);
  e) `--max-articles 0` disables the backstop (agent reviewer is sole judge);
  f) a within-cap plan is a NO-OP (no trim report written).
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _support

ASSEMBLE = _support.ASSEMBLE_SCRIPT
PLANNER_SCRIPTS = ASSEMBLE.parent


def _load_cap_module():
    """Import the assembler as a module for direct unit access to cap_articles."""
    return _support.load_module(ASSEMBLE, "assemble_wiki_skill_under_test")


# --- A pathological plan: 15 articles, 7 of them trimmable cap-*/concept-* ---
# 8 NON-TRIMMABLE — all 8 non-trimmable types, so "structural never dropped" is
# exercised by execution for every one of them (codereview LOW: the fixture
# previously carried only 4 of the 8, leaving runbook / domain-reference /
# design-pattern / agent-roster proven safe only by the hardcoded
# TRIMMABLE_TYPES tuple, never by a real plan running through the backstop):
#   product-overview, onboarding-maintainer (always-on)
#   architecture-overview, api-reference, domain-reference, design-pattern,
#   runbook, agent-roster (structural)
# + 5 capability + 2 concept = 15 trimmable-heavy total.
#
# Priorities are laid out non-trimmable-first (1..8) then trimmable (9..15) so
# the backstop, which drops lowest-priority-first, takes trimmable articles
# before it could ever reach a structural one — and a cap that bites only a few
# (TestBackstopEndToEnd uses 12) still drops a strict subset of trimmable,
# keeping the "lowest-priority-first" ordering meaningful.
def _pathological_plan():
    articles = [
        {"type": "product-overview", "slug": "big-repo-overview",
         "ref_file": "overview.md", "title": "Product Overview",
         "audience": "both", "priority": 1, "source_artifacts": ["survey.md"],
         "subject": "", "canonical_for": ["BIG-REPO-OVERVIEW"]},
        {"type": "onboarding-maintainer", "slug": "big-repo-onboard",
         "ref_file": "onboard.md", "title": "Maintainer Onboarding",
         "audience": "maintainer", "priority": 2, "source_artifacts": ["ops.md"],
         "subject": "", "canonical_for": ["BIG-REPO-ONBOARDING-MAINTAINER"]},
        {"type": "architecture-overview", "slug": "big-repo-arch",
         "ref_file": "arch.md", "title": "Architecture Overview",
         "audience": "maintainer", "priority": 3,
         "source_artifacts": ["architecture.md"], "subject": "",
         "canonical_for": ["BIG-REPO-ARCH"]},
        {"type": "api-reference", "slug": "big-repo-api",
         "ref_file": "api.md", "title": "API Reference",
         "audience": "both", "priority": 4, "source_artifacts": ["technical.md"],
         "subject": "", "canonical_for": ["BIG-REPO-API"]},
        {"type": "domain-reference", "slug": "big-repo-domain-reference",
         "ref_file": "domain.md", "title": "Domain Reference",
         "audience": "maintainer", "priority": 5, "source_artifacts": ["domain.md"],
         "subject": "", "canonical_for": ["BIG-REPO-DOMAIN"]},
        {"type": "design-pattern", "slug": "big-repo-repository-pattern",
         "ref_file": "pattern-repository.md", "title": "Pattern: Repository",
         "audience": "maintainer", "priority": 6,
         "source_artifacts": ["architecture.md"], "subject": "repository",
         "canonical_for": ["BIG-REPO-PATTERN-REPOSITORY"]},
        {"type": "runbook", "slug": "big-repo-migrate-runbook",
         "ref_file": "runbook-migrate.md", "title": "Runbook: Run Migrations",
         "audience": "maintainer", "priority": 7, "source_artifacts": ["ops.md"],
         "subject": "migrate", "canonical_for": ["BIG-REPO-RB-MIGRATE"]},
        {"type": "agent-roster", "slug": "big-repo-agent-roster",
         "ref_file": "agents.md", "title": "Agent & Skill Roster",
         "audience": "maintainer", "priority": 8, "source_artifacts": ["survey.md"],
         "subject": "", "canonical_for": ["BIG-REPO-AGENTS"]},
    ]
    # 5 capabilities (priority 9..13) + 2 concepts (priority 14..15) — trimmable.
    for i, feat in enumerate(["charge", "refund", "payout", "dispute", "settle"]):
        articles.append({
            "type": "capability", "slug": f"big-repo-cap-{feat}",
            "ref_file": f"cap-{feat}.md", "title": f"Capability: {feat.title()}",
            "audience": "both", "priority": 9 + i,
            "source_artifacts": ["domain.md"], "subject": feat,
            "canonical_for": [f"BIG-REPO-CAP-{feat.upper()}"],
        })
    for j, term in enumerate(["idempotency", "ledger"]):
        articles.append({
            "type": "concept-explanation", "slug": f"big-repo-concept-{term}",
            "ref_file": f"concept-{term}.md", "title": f'Concept: {term.title()}',
            "audience": "both", "priority": 14 + j,
            "source_artifacts": ["domain.md"], "subject": term,
            "canonical_for": [f"BIG-REPO-CONCEPT-{term.upper()}"],
        })
    return {
        "repo": "big-repo", "stack": "Python", "type": "service",
        "generated_at": "2026-06-17T00:00:00+00:00", "articles": articles,
    }


# Every NON-TRIMMABLE article type — 2 always-on + 6 structural = 8 of the 10
# types (the other 2, capability + concept-explanation, are TRIMMABLE_TYPES).
# The fixture above includes one article of each, so "structural never dropped"
# is now proven by execution for all 8, not just the original 4.
ALWAYS_ON_AND_STRUCTURAL = {
    "product-overview", "onboarding-maintainer",
    "architecture-overview", "api-reference",
    "domain-reference", "design-pattern", "runbook", "agent-roster",
}


class TestCapArticlesUnit(unittest.TestCase):
    """Direct unit tests of the deterministic cap function."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_cap_module()

    def test_caps_to_max_dropping_only_trimmable(self):
        articles = _pathological_plan()["articles"]
        kept, trimmed = self.mod.cap_articles(articles, 8)
        self.assertEqual(len(kept), 8, "did not cap to --max-articles=8")
        self.assertEqual(len(trimmed), 7, "expected exactly 7 trimmed (15 → 8)")
        # Only capability/concept-explanation may be dropped.
        for art in trimmed:
            self.assertIn(
                art["type"], self.mod.TRIMMABLE_TYPES,
                f"backstop dropped a non-trimmable article: {art['type']}",
            )

    def test_always_on_and_structural_never_dropped(self):
        articles = _pathological_plan()["articles"]
        kept, trimmed = self.mod.cap_articles(articles, 8)
        kept_types = {a["type"] for a in kept}
        for t in ALWAYS_ON_AND_STRUCTURAL:
            self.assertIn(t, kept_types, f"{t} was wrongly dropped by the backstop")

    def test_drops_lowest_priority_first(self):
        # Cap 12 over the 15-article plan drops the 3 worst by priority: the two
        # concepts (15 ledger, 14 idempotency) and the lowest capability
        # (13 settle) — a strict subset of the trimmable set, so this still proves
        # "lowest-priority-first" without forcing every trimmable out.
        articles = _pathological_plan()["articles"]
        kept, trimmed = self.mod.cap_articles(articles, 12)
        trimmed_prio = sorted(a["priority"] for a in trimmed)
        self.assertEqual(
            trimmed_prio, [13, 14, 15],
            f"expected the 3 lowest priorities dropped; got {trimmed_prio}",
        )
        # And every survivor in the structural floor is still present.
        kept_types = {a["type"] for a in kept}
        self.assertTrue(
            ALWAYS_ON_AND_STRUCTURAL <= kept_types,
            "a structural article was dropped before the trimmable set was exhausted",
        )

    def test_within_cap_is_noop(self):
        articles = _pathological_plan()["articles"][:8]
        kept, trimmed = self.mod.cap_articles(articles, 8)
        self.assertEqual(len(kept), 8)
        self.assertEqual(trimmed, [], "within-cap plan should not trim")

    def test_max_none_disables(self):
        articles = _pathological_plan()["articles"]
        kept, trimmed = self.mod.cap_articles(articles, None)
        self.assertEqual(len(kept), len(articles))
        self.assertEqual(trimmed, [])

    def test_never_drops_below_non_trimmable_floor(self):
        # max (2) smaller than the non-trimmable count (8): keep all 8
        # non-trimmable + nothing more is droppable past removing every
        # cap/concept article. Overflow above the cap is preserved, not dropped.
        articles = _pathological_plan()["articles"]
        kept, trimmed = self.mod.cap_articles(articles, 2)
        kept_types = {a["type"] for a in kept}
        for t in ALWAYS_ON_AND_STRUCTURAL:
            self.assertIn(t, kept_types, "non-trimmable floor was violated")
        # All 7 trimmable were dropped; the 8 non-trimmable remain.
        self.assertEqual(len(kept), 8)
        self.assertEqual(len(trimmed), 7)


class TestMalformedPlanDefensive(unittest.TestCase):
    """Explicit-null / wrong-type JSON values must degrade, never crash.

    Plans are LLM-authored JSON: a key can be present but explicitly `null`
    (`dict.get(key, default)` then returns None, NOT the default), and a list
    field can arrive as the wrong type. `dict.get("slug", "").strip()` and
    `sorted(..., key=lambda a: a.get("priority", 99))` both raise on such input
    (AttributeError on None.strip(); TypeError on None < int). These pin the
    guards that make the assembler tolerate it.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_cap_module()

    # --- canonical_id_for: explicit-null slug / canonical_for ---

    def test_canonical_id_explicit_null_slug_no_crash(self):
        # "slug": null → .get("slug", "") returns None; old code crashed on .strip().
        self.assertEqual(
            self.mod.canonical_id_for({"slug": None, "canonical_for": None}), ""
        )

    def test_canonical_id_missing_slug_no_crash(self):
        self.assertEqual(self.mod.canonical_id_for({}), "")

    def test_canonical_id_explicit_null_first_canonical_for_falls_back(self):
        # canonical_for present but first entry null → fall back to slug, not str(None).
        self.assertEqual(
            self.mod.canonical_id_for({"canonical_for": [None], "slug": "pay-x"}),
            "PAY-X",
        )

    def test_canonical_id_string_slug_still_uppercased(self):
        self.assertEqual(self.mod.canonical_id_for({"slug": "pay-x"}), "PAY-X")

    # --- cap_articles: non-list / explicit-null priority / non-dict member ---

    def test_cap_articles_non_list_returns_empty(self):
        for bad in (None, {}, "articles", 7):
            kept, trimmed = self.mod.cap_articles(bad, 8)
            self.assertEqual((kept, trimmed), ([], []), f"non-list {bad!r} not handled")

    def test_cap_articles_null_priority_does_not_crash_and_drops_first(self):
        # An explicit "priority": null trimmable article sorts as unranked (99) and
        # is dropped before a ranked one when the cap bites.
        articles = [
            {"type": "product-overview", "slug": "o", "ref_file": "o.md", "priority": 1},
            {"type": "capability", "slug": "c-null", "ref_file": "c-null.md",
             "priority": None, "canonical_for": ["X-CAP-NULL"]},
            {"type": "capability", "slug": "c-ranked", "ref_file": "c-ranked.md",
             "priority": 5, "canonical_for": ["X-CAP-RANKED"]},
        ]
        kept, trimmed = self.mod.cap_articles(articles, 2)
        self.assertEqual(len(trimmed), 1)
        self.assertEqual(trimmed[0]["slug"], "c-null",
                         "null-priority article should be dropped first (unranked)")
        kept_slugs = {a["slug"] for a in kept}
        self.assertEqual(kept_slugs, {"o", "c-ranked"})

    def test_cap_articles_tolerates_non_dict_member(self):
        # A malformed list with a stray non-dict entry must not raise; the non-dict
        # is non-trimmable (article_type → None) so it is kept, ranked last.
        articles = [
            {"type": "capability", "slug": "c1", "ref_file": "c1.md", "priority": 5,
             "canonical_for": ["X-CAP-1"]},
            "i-am-not-a-dict",
            {"type": "capability", "slug": "c2", "ref_file": "c2.md", "priority": 6,
             "canonical_for": ["X-CAP-2"]},
        ]
        kept, trimmed = self.mod.cap_articles(articles, 2)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(trimmed), 1)
        self.assertIn("i-am-not-a-dict", kept, "non-dict member was wrongly dropped")

    def test_article_priority_helper_coerces_bad_values(self):
        self.assertEqual(self.mod.article_priority({"priority": 3}), 3)
        self.assertEqual(self.mod.article_priority({"priority": None}),
                         self.mod.UNRANKED_PRIORITY)
        self.assertEqual(self.mod.article_priority({"priority": "high"}),
                         self.mod.UNRANKED_PRIORITY)
        self.assertEqual(self.mod.article_priority({}), self.mod.UNRANKED_PRIORITY)
        self.assertEqual(self.mod.article_priority("not-a-dict"),
                         self.mod.UNRANKED_PRIORITY)


class TestMalformedPlanEndToEnd(unittest.TestCase):
    """The real assembler must exit 0 on a plan with explicit-null priorities.

    Reproduces the latent crash the cap fix alone would NOT have caught: even
    after cap_articles is guarded, main()'s `sorted(articles, ...)` for the Load
    guide + article table would still hit `None < int` on a surviving article
    whose priority is explicitly null. This drives the script end-to-end with
    such a plan and asserts a written router, no traceback.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        artifacts = tmp / "artifacts"
        artifacts.mkdir()
        (artifacts / "survey.md").write_text("# Survey\n## Purpose & Context\nA service.\n")
        # A small, within-cap plan so the backstop is a no-op — isolating the
        # main() sort path. Two articles carry an explicit null priority; one omits
        # priority entirely; one omits slug. None of these may crash the assembler.
        plan = {
            "repo": "null-prio-repo", "stack": "Python", "type": "service",
            "generated_at": "2026-06-17T00:00:00+00:00",
            "articles": [
                {"type": "product-overview", "slug": "np-overview",
                 "ref_file": "overview.md", "title": "Overview", "audience": "both",
                 "priority": None, "canonical_for": ["NP-OVERVIEW"]},
                {"type": "architecture-overview", "slug": None,
                 "ref_file": "arch.md", "title": "Architecture", "audience": "maintainer",
                 "canonical_for": ["NP-ARCH"]},
                {"type": "capability", "slug": "np-cap-x", "ref_file": "cap-x.md",
                 "title": "Capability: X", "audience": "both", "priority": None,
                 "subject": "x", "canonical_for": ["NP-CAP-X"]},
            ],
        }
        cls.plan_path = tmp / "null-prio-repo-wiki-plan.json"
        cls.plan_path.write_text(json.dumps(plan))
        cls.staging = tmp / "null-prio-repo-wiki"
        cls.result = _support.run_script(
            ASSEMBLE,
            "--plan-file", cls.plan_path,
            "--skill-staging", cls.staging,
            "--artifacts-dir", artifacts,
            "--max-articles", "8",
            stdin=subprocess.DEVNULL,
        )
        cls.skill_path = cls.staging / "SKILL.md"
        cls.skill_text = cls.skill_path.read_text() if cls.skill_path.exists() else ""

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_exits_zero_no_traceback(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertNotIn("Traceback", self.result.stderr)
        self.assertNotIn("TypeError", self.result.stderr)
        self.assertNotIn("AttributeError", self.result.stderr)

    def test_router_written_with_all_refs(self):
        self.assertTrue(self.skill_path.exists(), "router not written on null-priority plan")
        linked = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        # All three plan articles must be linked despite their null/missing
        # priority + null slug. (The template may also emit static fallback refs
        # like `onboard.md` in the quick-ref when artifacts are sparse, so this is
        # a subset check, not exact-set equality.)
        self.assertTrue(
            {"overview.md", "arch.md", "cap-x.md"} <= linked,
            f"a plan article ref is missing from the router: {linked}",
        )


class TestBackstopEndToEnd(unittest.TestCase):
    """Drive the real assembler on a >8-article plan as a subprocess."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        artifacts = tmp / "artifacts"
        artifacts.mkdir()
        # Minimal artifacts — the assembler tolerates missing sections; the cap
        # path doesn't depend on artifact content.
        (artifacts / "survey.md").write_text("# Survey\n## Purpose & Context\nA service.\n")
        (artifacts / "domain.md").write_text("# Domain\n## Core Entities\n### Charge\n- **Represents**: a charge\n")
        (artifacts / "ops.md").write_text("# Ops\n")

        cls.plan_path = tmp / "big-repo-wiki-plan.json"
        cls.plan_path.write_text(json.dumps(_pathological_plan()))
        cls.report_path = cls.plan_path.with_name(cls.plan_path.stem + ".trim-report.json")
        cls.staging = tmp / "big-repo-wiki"

        cls.result = _support.run_script(
            ASSEMBLE,
            "--plan-file", cls.plan_path,
            "--skill-staging", cls.staging,
            "--artifacts-dir", artifacts,
            "--max-articles", "8",
            stdin=subprocess.DEVNULL,  # proves no interactive prompt blocks
        )
        cls.skill_path = cls.staging / "SKILL.md"
        cls.skill_text = cls.skill_path.read_text() if cls.skill_path.exists() else ""
        cls.report = json.loads(cls.report_path.read_text()) if cls.report_path.exists() else None

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_proceeds_unattended_no_prompt(self):
        # (a) exit 0, router written, no human prompt — even with stdin closed.
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertTrue(self.skill_path.exists(), "router not written on a >8 plan")
        # The deleted human gate must not have come back as a stdout question.
        self.assertNotIn("> 8", self.result.stdout)
        self.assertNotRegex(
            self.result.stdout.lower(),
            r"confirm.*(plan|articles).*\?",
            "an interactive confirm prompt leaked to stdout",
        )

    def test_trim_report_lists_canonical_ids_for_reconciliation(self):
        # (d) the report enumerates trimmed canonical IDs so See-also can be fixed.
        self.assertIsNotNone(self.report, "no trim-report.json written on a >8 plan")
        self.assertEqual(self.report["capped_at"], 8)
        self.assertEqual(self.report["original_count"], 15)
        self.assertEqual(self.report["kept_count"], 8)
        self.assertEqual(self.report["trimmed_count"], 7)
        ids = self.report["trimmed_canonical_ids"]
        self.assertEqual(len(ids), 7)
        # Every trimmed ID is a CAP-/CONCEPT- id (never a structural/always-on one).
        for cid in ids:
            self.assertRegex(
                cid, r"-(CAP|CONCEPT)-",
                f"a non-trimmable canonical id was trimmed: {cid}",
            )

    def test_router_links_no_trimmed_ref(self):
        # (d cont.) the deterministic router must not link a dropped article's ref.
        linked = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        trimmed_refs = {a["ref_file"] for a in self.report["trimmed_articles"]}
        self.assertTrue(linked, "router produced no refs/*.md links")
        self.assertEqual(
            linked & trimmed_refs, set(),
            f"router links a trimmed ref (dead link): {linked & trimmed_refs}",
        )

    def test_kept_count_matches_router(self):
        # The router's Load guide should link exactly the kept articles' refs.
        linked = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        self.assertEqual(
            len(linked), 8,
            f"router should link the 8 kept articles, linked {len(linked)}: {linked}",
        )

    def test_all_non_trimmable_types_survive_into_router(self):
        # The codereview LOW this commit closes: drive ALL 8 non-trimmable types
        # through the REAL assembler and prove every one survives the backstop
        # into the router — not just the original 4. With 15 articles capped at 8,
        # the 7 trimmable are dropped and exactly the 8 non-trimmable remain, so
        # each of their refs (incl. domain.md, agents.md, pattern-*, runbook-*)
        # must appear in the Load guide.
        linked = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        non_trimmable_refs = {
            a["ref_file"]
            for a in _pathological_plan()["articles"]
            if a["type"] in ALWAYS_ON_AND_STRUCTURAL
        }
        # Sanity: the fixture really does carry all 8 non-trimmable types.
        self.assertEqual(
            len(non_trimmable_refs), len(ALWAYS_ON_AND_STRUCTURAL),
            "fixture must contribute one ref per non-trimmable type",
        )
        missing = non_trimmable_refs - linked
        self.assertEqual(
            missing, set(),
            f"a non-trimmable article was dropped from the router: {missing}",
        )

    def test_backstop_announced_on_stderr(self):
        self.assertIn("BACKSTOP", self.result.stderr)
        self.assertIn("max-articles", self.result.stderr)


def _batch_canonical_ids(article_texts):
    """All canonical IDs declared by `canonical_for:` across a batch of articles."""
    ids = set()
    for text in article_texts:
        capturing = False
        for line in text.splitlines():
            if line.startswith("canonical_for:"):
                capturing = True
                continue
            if capturing:
                m = re.match(r"\s*-\s*([A-Z0-9][A-Z0-9-]+)\s*$", line)
                if m:
                    ids.add(m.group(1))
                else:
                    capturing = False
    return ids


def _broken_references(article_text, batch_ids):
    """Deterministic mirror of the wiki-contract `broken_reference` lint.

    Returns the set of referenced canonical IDs that do NOT resolve to a
    canonical ID declared in the batch. Reads both the frontmatter
    `references:` list and `[#slug](...)`-style IDs cited in `## See also` rows
    (here, the `[ID]` token). A non-empty result means the lint fails.
    """
    referenced = set()
    # Frontmatter references: list.
    capturing = False
    for line in article_text.splitlines():
        if line.startswith("references:"):
            capturing = True
            continue
        if capturing:
            m = re.match(r"\s*-\s*([A-Z0-9][A-Z0-9-]+)\s*$", line)
            if m:
                referenced.add(m.group(1))
            else:
                capturing = False
    # `## See also` rows: `- [{CANONICAL-ID}](#slug) — why`
    in_see_also = False
    for line in article_text.splitlines():
        if re.match(r"^##\s+See also\s*$", line):
            in_see_also = True
            continue
        if in_see_also and re.match(r"^##\s+", line):
            break
        if in_see_also:
            for cid in re.findall(r"\[([A-Z0-9][A-Z0-9-]+)\]", line):
                referenced.add(cid)
    return referenced - batch_ids


class TestSeeAlsoReconciliationKeepsLintClean(unittest.TestCase):
    """Deterministically prove the trim path can keep `broken_reference` clean.

    The agent reviewer's prose reconciliation needs a live model, but the
    INVARIANT it must satisfy is deterministic and is pinned here: after a trim,
    a surviving article that still references a trimmed canonical ID FAILS the
    lint; dropping that `## See also` row + `references:` entry makes it PASS.
    This is exactly the reconciliation the trim-report's `trimmed_canonical_ids`
    drives.
    """

    SURVIVOR_WITH_DANGLING = """---
title: Domain Reference
slug: pay-domain-reference
canonical_for:
  - PAY-DOMAIN
references:
  - PAY-OVERVIEW
  - PAY-CAP-SETTLE
audience: maintainer
tier: 1
---

# Domain Reference

## Purpose
The canonical entities of pay.

## See also
- [PAY-OVERVIEW](#pay-overview) — the product overview
- [PAY-CAP-SETTLE](#pay-cap-settle) — how settlement works
"""

    SURVIVOR_RECONCILED = """---
title: Domain Reference
slug: pay-domain-reference
canonical_for:
  - PAY-DOMAIN
references:
  - PAY-OVERVIEW
audience: maintainer
tier: 1
---

# Domain Reference

## Purpose
The canonical entities of pay.

## See also
- [PAY-OVERVIEW](#pay-overview) — the product overview
"""

    OVERVIEW = """---
title: Product Overview
slug: pay-overview
canonical_for:
  - PAY-OVERVIEW
audience: both
tier: 1
---

# Product Overview

## Purpose
What pay is.
"""

    def test_dangling_reference_fails_lint(self):
        # PAY-CAP-SETTLE was trimmed (see TestBackstopEndToEnd); the batch now
        # has only OVERVIEW + the survivor, so the dangling ref must be flagged.
        batch = [self.OVERVIEW, self.SURVIVOR_WITH_DANGLING]
        ids = _batch_canonical_ids(batch)
        broken = _broken_references(self.SURVIVOR_WITH_DANGLING, ids)
        self.assertEqual(
            broken, {"PAY-CAP-SETTLE"},
            "the dangling reference to a trimmed article was not caught",
        )

    def test_reconciled_survivor_passes_lint(self):
        batch = [self.OVERVIEW, self.SURVIVOR_RECONCILED]
        ids = _batch_canonical_ids(batch)
        broken = _broken_references(self.SURVIVOR_RECONCILED, ids)
        self.assertEqual(
            broken, set(),
            f"reconciled survivor still has broken references: {broken}",
        )

    def test_trimmed_ids_are_exactly_what_must_be_reconciled(self):
        # Tie the lint back to the backstop: the IDs the report says to reconcile
        # are precisely the ones that, if left in a survivor, break the lint.
        trimmed_ids = {"PAY-CAP-SETTLE", "PAY-CONCEPT-IDEMPOTENCY", "PAY-CONCEPT-LEDGER"}
        batch = [self.OVERVIEW, self.SURVIVOR_WITH_DANGLING]
        ids = _batch_canonical_ids(batch)
        broken = _broken_references(self.SURVIVOR_WITH_DANGLING, ids)
        self.assertTrue(
            broken <= trimmed_ids,
            f"a broken ref {broken} was not in the trim report's reconcile list",
        )


class TestBackstopDisabled(unittest.TestCase):
    """--max-articles 0 disables the backstop (agent reviewer is sole judge)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        artifacts = tmp / "artifacts"
        artifacts.mkdir()
        (artifacts / "survey.md").write_text("# Survey\n")
        cls.plan_path = tmp / "big-repo-wiki-plan.json"
        cls.plan_path.write_text(json.dumps(_pathological_plan()))
        cls.report_path = cls.plan_path.with_name(cls.plan_path.stem + ".trim-report.json")
        cls.staging = tmp / "big-repo-wiki"
        cls.result = _support.run_script(
            ASSEMBLE,
            "--plan-file", cls.plan_path,
            "--skill-staging", cls.staging,
            "--artifacts-dir", artifacts,
            "--max-articles", "0",
            stdin=subprocess.DEVNULL,
        )
        cls.skill_text = (cls.staging / "SKILL.md").read_text()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_no_trim_when_disabled(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertFalse(
            self.report_path.exists(),
            "trim report written even though backstop was disabled (max=0)",
        )
        # All 15 articles' refs present.
        linked = set(re.findall(r"refs/([A-Za-z0-9._\-]+\.md)", self.skill_text))
        self.assertEqual(len(linked), 15, f"expected all 15 refs linked, got {len(linked)}")


if __name__ == "__main__":
    unittest.main()
