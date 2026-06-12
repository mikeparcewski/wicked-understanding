#!/usr/bin/env python3
"""
generate_viewer.py — Build a self-contained HTML wiki viewer from a
{repo}-wiki/ skill directory.

Usage:
    python3 generate_viewer.py \
        --skill-dir {repo}-wiki \
        --output {repo}-wiki-viewer.html

Reads all .md files from the skill directory's refs/ folder, embeds
them as JSON in a single HTML file. No server required — open in any
browser.

OFFLINE-SAFE: the Markdown renderer + syntax highlighter are inlined
from scripts/vendor/offline-md.js. The viewer has NO external CDN
dependency, so it renders fully (with highlighting) in air-gapped /
enterprise environments. There is intentionally zero `https://` script
or stylesheet reference in the generated HTML — see
tests/test_generate_viewer.py::test_no_external_cdn_references.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Inlined offline Markdown renderer + highlighter (replaces CDN marked.js +
# highlight.js). Bundled with the skill under scripts/vendor/ so generation
# never touches the network and the viewer runs fully offline.
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
OFFLINE_MD_JS = VENDOR_DIR / "offline-md.js"


# ── frontmatter parser ────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:].strip()
    meta = {}
    current_key = None
    multiline = []
    for line in fm_text.splitlines():
        if line.startswith("  ") and current_key and multiline is not None:
            multiline.append(line.strip())
            continue
        if ":" in line and not line.startswith(" "):
            if current_key and multiline:
                meta[current_key] = " ".join(multiline)
            k, _, v = line.partition(":")
            current_key = k.strip()
            v = v.strip().strip('"').strip("'").strip(">").strip()
            if v:
                meta[current_key] = v
                multiline = None
            else:
                multiline = []
    if current_key and multiline:
        meta[current_key] = " ".join(multiline)
    return meta, body


ARTICLE_ICONS = {
    "product-overview":       "📋",
    "architecture-overview":  "🏗️",
    "api-reference":          "🔌",
    "onboarding-maintainer":  "🚀",
    "capability":             "⚡",
    "concept-explanation":    "💡",
    "design-pattern":         "🔄",
    "runbook":                "🔧",
    "agent-roster":           "🤖",
}

ARTICLE_ORDER = [
    "product-overview", "architecture-overview", "api-reference",
    "onboarding-maintainer", "capability", "concept-explanation",
    "design-pattern", "runbook", "agent-roster",
]

CONFIDENCE_COLORS = {
    "HIGH":   "#10b981",
    "MEDIUM": "#f59e0b",
    "LOW":    "#ef4444",
}


def collect_articles(skill_dir: Path) -> list[dict]:
    """Collect all article .md files from the skill directory."""
    articles = []
    refs_dir = skill_dir / "refs"

    # Walk all .md files in refs/ (and subdirs)
    if refs_dir.exists():
        for md_path in sorted(refs_dir.rglob("*.md")):
            text = md_path.read_text()
            meta, body = parse_frontmatter(text)
            title = meta.get("title", md_path.stem.replace("-", " ").title())
            slug = meta.get("slug", md_path.stem)
            audience = meta.get("audience", "maintainer")
            tier = meta.get("tier", "1")
            canonical = meta.get("canonical_for", "")

            # Detect article type from canonical ID or filename
            article_type = "concept-explanation"
            for atype in ARTICLE_ICONS:
                if atype in slug or atype in str(md_path):
                    article_type = atype
                    break
            if "cap-" in md_path.stem or "cap_" in md_path.stem:
                article_type = "capability"
            if "concept-" in md_path.stem:
                article_type = "concept-explanation"
            if "arch" in md_path.stem:
                article_type = "architecture-overview"
            if "api" in md_path.stem:
                article_type = "api-reference"
            if "onboard" in md_path.stem:
                article_type = "onboarding-maintainer"
            if "overview" in md_path.stem:
                article_type = "product-overview"
            if "ops" in md_path.stem or "runbook" in md_path.stem:
                article_type = "runbook"
            if "pattern" in md_path.stem:
                article_type = "design-pattern"
            if "agent" in md_path.stem or "roster" in md_path.stem:
                article_type = "agent-roster"

            # Extract confidence from closer
            confidence = "MEDIUM"
            conf_match = re.search(r"##\s+Confidence\s*\n+(HIGH|MEDIUM|LOW)", text, re.IGNORECASE)
            if conf_match:
                confidence = conf_match.group(1).upper()

            articles.append({
                "id": md_path.stem,
                "title": title,
                "slug": slug,
                "type": article_type,
                "audience": audience,
                "confidence": confidence,
                "content": body,
                "icon": ARTICLE_ICONS.get(article_type, "📄"),
            })

    # Sort by article type order, then title
    type_order = {t: i for i, t in enumerate(ARTICLE_ORDER)}
    articles.sort(key=lambda a: (type_order.get(a["type"], 99), a["title"]))
    return articles


def get_repo_name(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text()
        meta, _ = parse_frontmatter(text)
        name = meta.get("name", skill_dir.name)
        return name.replace("-wiki", "").replace("-", " ").title()
    return skill_dir.name.replace("-wiki", "").replace("-", " ").title()


def generate_html(skill_dir: Path, output_path: Path):
    articles = collect_articles(skill_dir)
    repo_name = get_repo_name(skill_dir)

    if not articles:
        print("Warning: no article files found in refs/. Is the skill directory correct?", file=sys.stderr)

    articles_json = json.dumps(articles, ensure_ascii=False)

    # Read the offline Markdown renderer + highlighter to inline it. This is the
    # offline-safety guarantee: the libraries ship INSIDE the HTML, not from a CDN.
    try:
        offline_md_js = OFFLINE_MD_JS.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: offline renderer not found at {OFFLINE_MD_JS}: {exc}", file=sys.stderr)
        sys.exit(1)
    # Guard against a stray closing </script> in the vendored source breaking
    # the inline <script> block (defensive; the vendored file has none).
    offline_md_js = offline_md_js.replace("</script>", "<\\/script>")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{repo_name} Wiki</title>
<!-- Offline-safe: Markdown renderer + highlighter are inlined below; NO CDN. -->
<script>
{offline_md_js}
</script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --sidebar-w: 260px;
    --topbar-h: 52px;
    --bg: #f1f5f9;
    --surface: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --text-muted: #64748b;
    --accent: #3b82f6;
    --accent-light: #eff6ff;
    --radius: 8px;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: "SF Mono", "Fira Code", "Cascadia Code", monospace;
  }}

  body {{ font-family: var(--font-sans); background: var(--bg); color: var(--text);
         display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}

  /* ── Top bar ── */
  .topbar {{ height: var(--topbar-h); background: var(--surface); border-bottom: 1px solid var(--border);
             display: flex; align-items: center; gap: 12px; padding: 0 16px;
             flex-shrink: 0; z-index: 10; }}
  .topbar-logo {{ font-weight: 700; font-size: 15px; color: var(--text); white-space: nowrap; }}
  .topbar-logo span {{ color: var(--accent); }}
  .topbar-search {{ flex: 1; max-width: 400px; position: relative; }}
  .topbar-search input {{
    width: 100%; height: 34px; border: 1px solid var(--border); border-radius: 6px;
    padding: 0 12px 0 34px; font-size: 13px; color: var(--text); background: var(--bg);
    outline: none; transition: border-color .15s;
  }}
  .topbar-search input:focus {{ border-color: var(--accent); background: #fff; }}
  .topbar-search::before {{ content: "🔍"; position: absolute; left: 10px; top: 7px; font-size: 13px; }}
  .topbar-meta {{ margin-left: auto; font-size: 12px; color: var(--text-muted); white-space: nowrap; }}

  /* ── Layout ── */
  .layout {{ display: flex; flex: 1; overflow: hidden; }}

  /* ── Sidebar ── */
  .sidebar {{ width: var(--sidebar-w); background: var(--surface); border-right: 1px solid var(--border);
              display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto; }}
  .sidebar-section {{ padding: 8px 0; }}
  .sidebar-group {{ padding: 6px 12px 2px; font-size: 10px; font-weight: 700; letter-spacing: .08em;
                    color: var(--text-muted); text-transform: uppercase; }}
  .sidebar-item {{
    display: flex; align-items: center; gap: 8px; padding: 7px 14px;
    cursor: pointer; font-size: 13px; color: var(--text); border-left: 3px solid transparent;
    transition: background .1s, border-color .1s; user-select: none;
    text-decoration: none;
  }}
  .sidebar-item:hover {{ background: var(--bg); }}
  .sidebar-item.active {{ background: var(--accent-light); border-left-color: var(--accent);
                          color: var(--accent); font-weight: 500; }}
  .sidebar-icon {{ flex-shrink: 0; font-size: 14px; }}
  .sidebar-badge {{
    margin-left: auto; font-size: 10px; font-weight: 600; padding: 1px 6px;
    border-radius: 10px; flex-shrink: 0;
  }}
  .badge-maintainer {{ background: #f1f5f9; color: #64748b; }}
  .badge-both {{ background: #ecfdf5; color: #059669; }}
  .badge-user {{ background: #eff6ff; color: #3b82f6; }}

  .no-results {{ padding: 20px 14px; font-size: 13px; color: var(--text-muted); text-align: center; }}

  /* ── Main content ── */
  .main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
  .article-header {{
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 14px 24px; display: flex; align-items: center; gap: 10px; flex-shrink: 0;
  }}
  .article-icon {{ font-size: 20px; }}
  .article-title {{ font-size: 16px; font-weight: 600; flex: 1; }}
  .conf-badge {{
    font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 12px; color: #fff;
  }}
  .aud-badge {{
    font-size: 11px; padding: 3px 8px; border-radius: 12px;
    background: var(--bg); color: var(--text-muted); border: 1px solid var(--border);
  }}

  .article-body {{ flex: 1; overflow-y: auto; padding: 32px 40px; max-width: 900px; }}

  /* ── Empty state ── */
  .empty-state {{
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 12px; color: var(--text-muted);
  }}
  .empty-state h2 {{ font-size: 18px; color: var(--text); }}
  .empty-state p {{ font-size: 14px; max-width: 360px; text-align: center; line-height: 1.5; }}

  /* ── Markdown styles ── */
  .article-body h1 {{ font-size: 22px; font-weight: 700; margin: 0 0 20px; color: var(--text); }}
  .article-body h2 {{ font-size: 17px; font-weight: 600; margin: 28px 0 12px;
                      padding-bottom: 6px; border-bottom: 1px solid var(--border); }}
  .article-body h3 {{ font-size: 14px; font-weight: 600; margin: 20px 0 8px; }}
  .article-body p {{ font-size: 14px; line-height: 1.7; margin-bottom: 14px; color: #334155; }}
  .article-body ul, .article-body ol {{ padding-left: 22px; margin-bottom: 14px; }}
  .article-body li {{ font-size: 14px; line-height: 1.7; margin-bottom: 4px; color: #334155; }}
  .article-body blockquote {{
    border-left: 3px solid var(--accent); margin: 16px 0; padding: 8px 16px;
    background: var(--accent-light); border-radius: 0 6px 6px 0; color: #1e3a8a;
    font-size: 13px; font-style: italic;
  }}
  .article-body code {{
    font-family: var(--font-mono); font-size: 12.5px; background: #f8fafc;
    padding: 1px 5px; border-radius: 4px; border: 1px solid var(--border); color: #be185d;
  }}
  .article-body pre {{
    background: #0f172a; border-radius: 8px; padding: 16px; margin: 16px 0;
    overflow-x: auto; position: relative;
  }}
  .article-body pre code {{ background: none; border: none; padding: 0; color: #e2e8f0; font-size: 13px; }}

  /* ── Inline syntax-highlight theme (offline; replaces highlight.js CDN CSS) ── */
  .article-body pre code.hljs {{ color: #e2e8f0; }}
  .hljs-comment {{ color: #94a3b8; font-style: italic; }}
  .hljs-string  {{ color: #86efac; }}
  .hljs-number  {{ color: #fca5a5; }}
  .hljs-keyword {{ color: #93c5fd; font-weight: 600; }}
  .copy-btn {{
    position: absolute; top: 8px; right: 8px; background: rgba(255,255,255,.1);
    border: 1px solid rgba(255,255,255,.2); color: #94a3b8; font-size: 11px;
    padding: 3px 8px; border-radius: 4px; cursor: pointer; transition: all .15s;
  }}
  .copy-btn:hover {{ background: rgba(255,255,255,.2); color: #fff; }}
  .copy-btn.copied {{ color: #4ade80; border-color: #4ade80; }}

  .article-body table {{
    width: 100%; border-collapse: collapse; font-size: 13px;
    margin: 16px 0; display: block; overflow-x: auto;
  }}
  .article-body th {{
    background: #f8fafc; text-align: left; padding: 8px 12px; font-weight: 600;
    border: 1px solid var(--border); white-space: nowrap;
  }}
  .article-body td {{ padding: 8px 12px; border: 1px solid var(--border); vertical-align: top; line-height: 1.5; }}
  .article-body tr:nth-child(even) td {{ background: #fafafa; }}
  .article-body hr {{ border: none; border-top: 1px solid var(--border); margin: 24px 0; }}
  .article-body a {{ color: var(--accent); text-decoration: none; }}
  .article-body a:hover {{ text-decoration: underline; }}

  /* src citation styling */
  .src-cite {{ font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);
               background: #f8fafc; border: 1px solid var(--border); padding: 1px 5px;
               border-radius: 3px; white-space: nowrap; }}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">📖 <span>{repo_name}</span> Wiki</div>
  <div class="topbar-search">
    <input type="text" id="search" placeholder="Search articles…" oninput="filterArticles(this.value)">
  </div>
  <div class="topbar-meta" id="article-count">{len(articles)} articles</div>
</div>

<div class="layout">
  <nav class="sidebar" id="sidebar">
    <div id="sidebar-content"></div>
  </nav>
  <main class="main" id="main">
    <div class="empty-state" id="empty-state">
      <div style="font-size:48px">📖</div>
      <h2>Select an article</h2>
      <p>Choose a topic from the sidebar to start reading. Use the search box to filter by keyword.</p>
    </div>
    <div id="article-view" style="display:none;flex-direction:column;flex:1;overflow:hidden;">
      <div class="article-header">
        <span class="article-icon" id="art-icon"></span>
        <span class="article-title" id="art-title"></span>
        <span class="aud-badge" id="art-aud"></span>
        <span class="conf-badge" id="art-conf"></span>
      </div>
      <div class="article-body" id="art-body"></div>
    </div>
  </main>
</div>

<script>
const ARTICLES = {articles_json};

// ── Group articles by type ────────────────────────────────────────────────────

const TYPE_LABELS = {{
  'product-overview':      'Overview',
  'architecture-overview': 'Architecture',
  'api-reference':         'API Reference',
  'onboarding-maintainer': 'Onboarding',
  'capability':            'Capabilities',
  'concept-explanation':   'Concepts',
  'design-pattern':        'Patterns',
  'runbook':               'Runbooks',
  'agent-roster':          'Agent Roster',
}};

const CONF_COLORS = {{
  'HIGH':   '#10b981',
  'MEDIUM': '#f59e0b',
  'LOW':    '#ef4444',
}};

const TYPE_ORDER = [
  'product-overview','architecture-overview','api-reference','onboarding-maintainer',
  'capability','concept-explanation','design-pattern','runbook','agent-roster'
];

let currentId = null;

function groupArticles(articles) {{
  const groups = {{}};
  for (const a of articles) {{
    const g = a.type;
    if (!groups[g]) groups[g] = [];
    groups[g].push(a);
  }}
  return groups;
}}

function buildSidebar(articles) {{
  const groups = groupArticles(articles);
  const container = document.getElementById('sidebar-content');
  container.innerHTML = '';

  const orderedTypes = [...new Set([...TYPE_ORDER, ...Object.keys(groups)])];
  let anyGroup = false;

  for (const type of orderedTypes) {{
    if (!groups[type]) continue;
    anyGroup = true;
    const section = document.createElement('div');
    section.className = 'sidebar-section';

    const label = document.createElement('div');
    label.className = 'sidebar-group';
    label.textContent = TYPE_LABELS[type] || type;
    section.appendChild(label);

    for (const a of groups[type]) {{
      const item = document.createElement('div');
      item.className = 'sidebar-item' + (a.id === currentId ? ' active' : '');
      item.dataset.id = a.id;
      item.onclick = () => showArticle(a.id);

      const icon = document.createElement('span');
      icon.className = 'sidebar-icon';
      icon.textContent = a.icon;

      const title = document.createElement('span');
      title.style.flex = '1';
      title.textContent = a.title.replace(/ — .*/, '').replace(/.*— /, '');

      const badge = document.createElement('span');
      badge.className = `sidebar-badge badge-${{a.audience.replace(/[^a-z]/g,'')}}`;
      badge.textContent = a.audience === 'both' ? '👥' : a.audience === 'user' ? 'U' : 'M';

      item.appendChild(icon);
      item.appendChild(title);
      item.appendChild(badge);
      section.appendChild(item);
    }}

    container.appendChild(section);
  }}

  if (!anyGroup) {{
    const msg = document.createElement('div');
    msg.className = 'no-results';
    msg.textContent = 'No articles match.';
    container.appendChild(msg);
  }}
}}

function filterArticles(query) {{
  const q = query.toLowerCase().trim();
  if (!q) {{
    buildSidebar(ARTICLES);
    document.getElementById('article-count').textContent = `${{ARTICLES.length}} articles`;
    return;
  }}
  const filtered = ARTICLES.filter(a =>
    a.title.toLowerCase().includes(q) ||
    a.content.toLowerCase().includes(q) ||
    a.type.includes(q)
  );
  buildSidebar(filtered);
  document.getElementById('article-count').textContent = `${{filtered.length}} of ${{ARTICLES.length}} articles`;
}}

// ── Markdown rendering ────────────────────────────────────────────────────────

marked.setOptions({{ breaks: true, gfm: true }});

function styleSourceCites(html) {{
  // Highlight [src: file:path] citations
  const CITE_RE = new RegExp('\\\\[src:\\\\s*([^\\\\]]+)\\\\]', 'g');
  return html.replace(CITE_RE,
    (m, cite) => `<code class="src-cite">[src: ${{cite.trim()}}]</code>`
  );
}}

function addCopyButtons(container) {{
  container.querySelectorAll('pre').forEach(pre => {{
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.onclick = async () => {{
      const code = pre.querySelector('code');
      await navigator.clipboard.writeText(code ? code.innerText : pre.innerText);
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {{ btn.textContent = 'Copy'; btn.classList.remove('copied'); }}, 1800);
    }};
    pre.style.position = 'relative';
    pre.appendChild(btn);
  }});
}}

function showArticle(id) {{
  const article = ARTICLES.find(a => a.id === id);
  if (!article) return;
  currentId = id;

  // Update sidebar active state
  document.querySelectorAll('.sidebar-item').forEach(el => {{
    el.classList.toggle('active', el.dataset.id === id);
  }});

  // Show article view
  document.getElementById('empty-state').style.display = 'none';
  const view = document.getElementById('article-view');
  view.style.display = 'flex';

  // Header
  document.getElementById('art-icon').textContent = article.icon;
  document.getElementById('art-title').textContent = article.title;
  const audEl = document.getElementById('art-aud');
  audEl.textContent = article.audience;
  audEl.className = `aud-badge badge-${{article.audience.replace(/[^a-z]/g,'')}}`;
  const confEl = document.getElementById('art-conf');
  confEl.textContent = article.confidence;
  confEl.style.background = CONF_COLORS[article.confidence] || '#64748b';

  // Render markdown
  const body = document.getElementById('art-body');
  body.scrollTop = 0;
  let html = marked.parse(article.content);
  html = styleSourceCites(html);
  body.innerHTML = html;

  // Syntax highlight
  body.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
  addCopyButtons(body);

  // Update page title
  document.title = `${{article.title}} — {repo_name} Wiki`;
}}

// ── Keyboard navigation ───────────────────────────────────────────────────────

document.addEventListener('keydown', e => {{
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
    e.preventDefault();
    document.getElementById('search').focus();
  }}
  if (e.key === 'Escape') {{
    document.getElementById('search').value = '';
    filterArticles('');
    document.getElementById('search').blur();
  }}
}});

// ── Init ──────────────────────────────────────────────────────────────────────

buildSidebar(ARTICLES);
if (ARTICLES.length > 0) showArticle(ARTICLES[0].id);
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    size_kb = output_path.stat().st_size // 1024
    print(f"Wrote {output_path} ({size_kb}KB, {len(articles)} articles)")


def main():
    parser = argparse.ArgumentParser(description="Generate static HTML wiki viewer from skill directory")
    parser.add_argument("--skill-dir", required=True, help="Path to {repo}-wiki/ skill directory")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir)
    output_path = Path(args.output)

    if not skill_dir.exists():
        print(f"Error: skill directory not found: {skill_dir}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_html(skill_dir, output_path)


if __name__ == "__main__":
    main()
