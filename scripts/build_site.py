#!/usr/bin/env python3
"""Build static site from digests/*.md → docs/ (GitHub Pages /docs)."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"
DOCS = ROOT / "docs"


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" rel="noopener" target="_blank">\1</a>',
        s,
    )
    return s


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            out.append(f"<li>{_inline(line[2:].strip())}</li>")
        elif line.strip() == "---":
            out.append("<hr/>")
        elif not line.strip():
            out.append("")
        else:
            out.append(f"<p>{_inline(line)}</p>")
    joined = "\n".join(out)
    joined = re.sub(
        r"(?:<li>.*?</li>\n?)+",
        lambda m: "<ul>\n" + m.group(0) + "</ul>\n",
        joined,
        flags=re.S,
    )
    return joined


def shell(title: str, body: str) -> str:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="style.css"/>
</head>
<body>
  <header class="top">
    <a class="brand" href="index.html">X Daily Digest</a>
    <nav>
      <a href="index.html">首页</a>
      <a href="https://github.com/DoTrungHuy/grok-daily-digest">源码</a>
    </nav>
  </header>
  <main class="container">
{body}
  </main>
  <footer class="foot">
    <p>X (twitter-cli Cookie) → DeepSeek → GitHub Pages · {html.escape(gen)}</p>
  </footer>
</body>
</html>
"""


CSS = """
:root { --bg:#0b0f14; --card:#121a22; --text:#e7eef7; --muted:#8aa0b5; --acc:#3d9cf0; --line:#1e2a36; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, sans-serif; background:var(--bg); color:var(--text); line-height:1.65; }
a { color:var(--acc); text-decoration:none; }
a:hover { text-decoration:underline; }
.top { display:flex; justify-content:space-between; align-items:center; padding:1rem 1.25rem; border-bottom:1px solid var(--line); position:sticky; top:0; background:rgba(11,15,20,.94); }
.brand { font-weight:700; color:var(--text); }
nav a { margin-left:1rem; color:var(--muted); }
.container { max-width:820px; margin:0 auto; padding:1.5rem 1.25rem 3rem; }
.hero h1 { margin:0 0 .5rem; font-size:1.75rem; }
.hero p { color:var(--muted); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:1rem 1.15rem; margin:.75rem 0; }
.card h2 { margin:0 0 .4rem; font-size:1.15rem; }
.meta { color:var(--muted); font-size:.9rem; }
.article h2 { margin-top:1.35rem; border-bottom:1px solid var(--line); padding-bottom:.3rem; }
.article code { background:#0b1219; padding:.1rem .35rem; border-radius:4px; }
.foot { border-top:1px solid var(--line); color:var(--muted); font-size:.85rem; padding:1.5rem; text-align:center; }
.badge { display:inline-block; background:#16324d; color:#9fd0ff; font-size:.75rem; padding:.15rem .5rem; border-radius:999px; }
"""


def build_site() -> Path:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")

    files = sorted(DIGESTS.glob("????-??-??.md"), reverse=True)
    cards = []
    for f in files:
        raw = f.read_text(encoding="utf-8")
        blurb = ""
        for line in raw.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("- **") or s == "---":
                continue
            blurb = s
            break
        cards.append(
            f"""<article class="card">
  <h2><a href="{f.stem}.html">{html.escape(f.stem)}</a></h2>
  <p class="meta"><span class="badge">digest</span></p>
  <p>{html.escape(blurb[:200])}{"…" if len(blurb) > 200 else ""}</p>
</article>"""
        )

    index_body = f"""
<section class="hero">
  <h1>每日 X 精读</h1>
  <p>免费 Cookie 读 X → DeepSeek 完整总结 → 自动发布。不使用付费 X API。</p>
</section>
<section>
{chr(10).join(cards) if cards else "<p class='meta'>暂无内容，等待流水线首次运行。</p>"}
</section>
"""
    (DOCS / "index.html").write_text(shell("X Daily Digest", index_body), encoding="utf-8")

    for f in files:
        body = md_to_html(f.read_text(encoding="utf-8"))
        page = shell(
            f"Digest {f.stem}",
            f'<article class="article card"><p class="meta"><a href="index.html">← 列表</a></p>{body}</article>',
        )
        (DOCS / f"{f.stem}.html").write_text(page, encoding="utf-8")

    return DOCS


if __name__ == "__main__":
    print(build_site())
