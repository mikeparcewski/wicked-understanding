/*
 * offline-md.js — minimal, dependency-free Markdown renderer + syntax
 * highlighter, inlined into the generated wiki viewer so it renders fully
 * OFFLINE with NO external CDN dependency (air-gapped / enterprise safe).
 *
 * This replaces the previous CDN-loaded marked.js + highlight.js. It exposes
 * the SAME minimal surface the viewer calls:
 *   - window.marked.setOptions(opts)   (no-op shim; options are ignored)
 *   - window.marked.parse(markdown) -> html string
 *   - window.hljs.highlightElement(el) (lightweight token highlighting)
 *
 * It is intentionally small and self-contained. It supports the GitHub-
 * flavoured Markdown the wiki articles actually use: headings, bold/italic,
 * inline code, fenced + indented code blocks, links, images, blockquotes,
 * ordered/unordered lists (with nesting), tables, horizontal rules, and
 * paragraphs. It degrades gracefully (renders text, never raw markdown
 * markup) for anything it does not recognise — it never falls back to
 * showing unrendered markdown the way a missing CDN script would.
 *
 * NOT a spec-complete Markdown engine. If full marked.js fidelity is ever
 * required, vendor marked.min.js + highlight.min.js as local files in this
 * directory and inline those instead — the contract that matters is "no
 * runtime external network dependency", which both approaches satisfy.
 */
(function () {
  "use strict";

  // ── HTML escaping ──────────────────────────────────────────────────────────
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Inline span rendering (run on already-escaped text) ─────────────────────
  // Order matters: code spans first so their contents are not re-formatted.
  function renderInline(text) {
    // Inline code: `code`  (capture lazily, no backticks inside)
    text = text.replace(/`([^`]+)`/g, function (_m, code) {
      return "<code>" + code + "</code>";
    });
    // Images: ![alt](src)
    text = text.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g,
      function (_m, alt, src) {
        return '<img alt="' + alt + '" src="' + src + '">';
      });
    // Links: [text](href)
    text = text.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g,
      function (_m, label, href) {
        return '<a href="' + href + '">' + label + "</a>";
      });
    // Bold: **text** or __text__
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    // Italic: *text* or _text_  (avoid matching ** already consumed)
    text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    text = text.replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");
    // Strikethrough: ~~text~~
    text = text.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    return text;
  }

  // ── Table parsing ───────────────────────────────────────────────────────────
  function isTableSep(line) {
    return /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$/.test(line);
  }
  function splitRow(line) {
    var t = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    return t.split("|").map(function (c) { return c.trim(); });
  }

  // ── Block parser ────────────────────────────────────────────────────────────
  function parse(src) {
    if (src == null) return "";
    var lines = String(src).replace(/\r\n?/g, "\n").split("\n");
    var out = [];
    var i = 0;

    function flushParagraph(buf) {
      if (buf.length) {
        out.push("<p>" + renderInline(esc(buf.join(" "))) + "</p>");
      }
    }

    while (i < lines.length) {
      var line = lines[i];

      // Fenced code block: ``` or ~~~ with optional language
      var fence = line.match(/^\s*(```+|~~~+)\s*([\w+-]*)\s*$/);
      if (fence) {
        var marker = fence[1][0];
        var lang = fence[2] || "";
        var code = [];
        i++;
        while (i < lines.length && !new RegExp("^\\s*" + marker + "{3,}\\s*$").test(lines[i])) {
          code.push(lines[i]);
          i++;
        }
        i++; // consume closing fence
        var cls = lang ? ' class="language-' + esc(lang) + '"' : "";
        out.push("<pre><code" + cls + ">" + esc(code.join("\n")) + "</code></pre>");
        continue;
      }

      // Indented code block (4 spaces / tab)
      if (/^( {4}|\t)/.test(line) && line.trim() !== "") {
        var icode = [];
        while (i < lines.length && (/^( {4}|\t)/.test(lines[i]) || lines[i].trim() === "")) {
          // stop if a blank line is followed by a non-indented line
          if (lines[i].trim() === "") {
            var j = i + 1;
            if (j < lines.length && !/^( {4}|\t)/.test(lines[j])) break;
          }
          icode.push(lines[i].replace(/^( {4}|\t)/, ""));
          i++;
        }
        out.push("<pre><code>" + esc(icode.join("\n").replace(/\n+$/, "")) + "</code></pre>");
        continue;
      }

      // ATX heading
      var h = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
      if (h) {
        var lvl = h[1].length;
        out.push("<h" + lvl + ">" + renderInline(esc(h[2])) + "</h" + lvl + ">");
        i++;
        continue;
      }

      // Horizontal rule
      if (/^\s*([-*_])\s*(\1\s*){2,}$/.test(line)) {
        out.push("<hr>");
        i++;
        continue;
      }

      // Blockquote
      if (/^\s*>/.test(line)) {
        var quote = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) {
          quote.push(lines[i].replace(/^\s*>\s?/, ""));
          i++;
        }
        out.push("<blockquote>" + parse(quote.join("\n")) + "</blockquote>");
        continue;
      }

      // Table
      if (line.indexOf("|") !== -1 && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        var header = splitRow(line);
        i += 2; // skip header + separator
        var rows = [];
        while (i < lines.length && lines[i].indexOf("|") !== -1 && lines[i].trim() !== "") {
          rows.push(splitRow(lines[i]));
          i++;
        }
        var thtml = "<table><thead><tr>";
        header.forEach(function (c) { thtml += "<th>" + renderInline(esc(c)) + "</th>"; });
        thtml += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          thtml += "<tr>";
          for (var c = 0; c < header.length; c++) {
            thtml += "<td>" + renderInline(esc(r[c] || "")) + "</td>";
          }
          thtml += "</tr>";
        });
        thtml += "</tbody></table>";
        out.push(thtml);
        continue;
      }

      // Lists (ordered / unordered), with simple one-level nesting
      var listItem = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
      if (listItem) {
        var ordered = /\d/.test(listItem[2]);
        var tag = ordered ? "ol" : "ul";
        var items = [];
        var baseIndent = listItem[1].length;
        while (i < lines.length) {
          var m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
          if (m && m[1].length >= baseIndent) {
            items.push(renderInline(esc(m[3])));
            i++;
          } else if (lines[i].trim() === "") {
            // allow a single trailing blank inside a list, then stop if list ends
            var k = i + 1;
            if (k < lines.length && lines[k].match(/^(\s*)([-*+]|\d+[.)])\s+/)) {
              i++;
            } else {
              break;
            }
          } else {
            break;
          }
        }
        var lhtml = "<" + tag + ">";
        items.forEach(function (it) { lhtml += "<li>" + it + "</li>"; });
        lhtml += "</" + tag + ">";
        out.push(lhtml);
        continue;
      }

      // Blank line — paragraph boundary
      if (line.trim() === "") {
        i++;
        continue;
      }

      // Paragraph: accumulate consecutive non-special lines
      var para = [];
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !/^\s*(```+|~~~+)/.test(lines[i]) &&
        !/^(#{1,6})\s+/.test(lines[i]) &&
        !/^\s*>/.test(lines[i]) &&
        !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) &&
        !/^\s*([-*_])\s*(\1\s*){2,}$/.test(lines[i]) &&
        !(lines[i].indexOf("|") !== -1 && i + 1 < lines.length && isTableSep(lines[i + 1]))
      ) {
        para.push(lines[i].trim());
        i++;
      }
      flushParagraph(para);
    }

    return out.join("\n");
  }

  // ── marked shim ──────────────────────────────────────────────────────────────
  var marked = {
    setOptions: function () { /* options ignored — minimal renderer */ },
    parse: parse,
  };

  // ── hljs shim — lightweight, language-agnostic token highlighting ────────────
  // Highlights strings, comments, numbers, and a common keyword set. Good enough
  // for readability offline; does not depend on per-language grammars.
  var KEYWORD_LIST = [
    "function", "return", "const", "let", "var", "if", "else", "for", "while",
    "import", "from", "export", "default", "class", "extends", "new", "this",
    "async", "await", "try", "catch", "finally", "throw", "switch", "case",
    "break", "continue", "def", "lambda", "pass", "raise", "with", "as",
    "print", "True", "False", "None", "null", "true", "false",
    "public", "private", "protected", "static", "void", "int", "string", "bool",
    "func", "package", "type", "struct", "interface", "go", "defer", "chan",
    "fn", "impl", "trait", "mut", "pub", "use", "match", "enum", "self",
  ].join("|");
  var KEYWORDS = new RegExp("^(?:" + KEYWORD_LIST + ")$");

  // Single-pass tokenizer: walk the RAW source left-to-right and emit escaped,
  // span-wrapped HTML. Doing it in one pass (rather than chained regex replaces
  // over already-emitted markup) prevents the keyword/string passes from
  // re-matching inside span tags they just inserted.
  function highlightCode(text) {
    var src = String(text);
    var out = "";
    var n = src.length;
    var idx = 0;

    function wrap(cls, raw) { return '<span class="' + cls + '">' + esc(raw) + "</span>"; }

    var WORD = /[A-Za-z_$][A-Za-z0-9_$]*/y;
    var NUM = /\d+(?:\.\d+)?/y;

    while (idx < n) {
      var ch = src[idx];

      // Block comment /* ... */
      if (ch === "/" && src[idx + 1] === "*") {
        var end = src.indexOf("*/", idx + 2);
        if (end === -1) end = n - 2;
        out += wrap("hljs-comment", src.slice(idx, end + 2));
        idx = end + 2;
        continue;
      }
      // Line comment // ... or # ... (to end of line)
      if ((ch === "/" && src[idx + 1] === "/") || ch === "#") {
        var nl = src.indexOf("\n", idx);
        if (nl === -1) nl = n;
        out += wrap("hljs-comment", src.slice(idx, nl));
        idx = nl;
        continue;
      }
      // Strings: " ... ", ' ... ', ` ... `  (with simple backslash escaping)
      if (ch === '"' || ch === "'" || ch === "`") {
        var q = ch;
        var j = idx + 1;
        while (j < n && src[j] !== q) {
          if (src[j] === "\\") j++; // skip escaped char
          j++;
        }
        j = Math.min(j + 1, n);
        out += wrap("hljs-string", src.slice(idx, j));
        idx = j;
        continue;
      }
      // Numbers
      NUM.lastIndex = idx;
      var nm = NUM.exec(src);
      if (nm && nm.index === idx && /\d/.test(ch)) {
        out += wrap("hljs-number", nm[0]);
        idx += nm[0].length;
        continue;
      }
      // Identifiers / keywords
      WORD.lastIndex = idx;
      var wm = WORD.exec(src);
      if (wm && wm.index === idx) {
        var word = wm[0];
        if (KEYWORDS.test(word)) {
          out += wrap("hljs-keyword", word);
        } else {
          out += esc(word);
        }
        idx += word.length;
        continue;
      }
      // Any other single character
      out += esc(ch);
      idx++;
    }
    return out;
  }

  var hljs = {
    highlightElement: function (el) {
      if (!el) return;
      if (el.dataset && el.dataset.highlighted === "yes") return;
      var raw = el.textContent;
      el.innerHTML = highlightCode(raw);
      el.classList.add("hljs");
      if (el.dataset) el.dataset.highlighted = "yes";
    },
    // Compatibility no-ops for older highlight.js call sites.
    highlightAll: function () {
      var nodes = document.querySelectorAll("pre code");
      for (var i = 0; i < nodes.length; i++) this.highlightElement(nodes[i]);
    },
    configure: function () {},
  };

  window.marked = marked;
  window.hljs = hljs;
})();
