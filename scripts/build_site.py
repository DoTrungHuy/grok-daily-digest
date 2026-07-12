#!/usr/bin/env python3
"""Build static digest site → docs/ (GitHub Pages).

UI direction (practical + polished):
  Linear.app blog / changelog calm dark + editorial newsletter layout.
  NOT cinematic liquid-glass landing pages (poor fit for daily reading).

References:
  - Linear blog dark typography & spacing
  - Editorial magazine item numbering
  - Calm dark UI: flat surfaces, gray scale, sparse accent
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"
DOCS = ROOT / "docs"
ASSET_VER = "20260712c"

_HEADER_RE = re.compile(r"^#\s+(.+)$", re.M)
_ITEM_SPLIT = re.compile(r"【ITEM(\d+)】")
_META_LINE = re.compile(r"^(时间窗|条目数|来自关注账号优先|信号强度)[：:]\s*(.+)$", re.M)
_URL_RE = re.compile(r"https?://[^\s,，)）]+")
_HANDLE_RE = re.compile(r"@[\w_]+")


@dataclass
class DigestItem:
    index: int
    title: str = ""
    category: str = ""
    quote: str = ""
    takeaway: str = ""
    source_raw: str = ""
    handles: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


@dataclass
class ParsedDigest:
    date: str
    title: str
    pipeline_meta: dict[str, str]
    hook: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    items: list[DigestItem] = field(default_factory=list)
    close: str = ""
    structured: bool = False
    raw_md: str = ""


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


def _extract_block(text: str, tag: str) -> str:
    m = re.search(
        rf"【{re.escape(tag)}】\s*(.*?)(?=【[A-Z0-9]+】|\Z)",
        text,
        re.S,
    )
    return m.group(1).strip() if m else ""


def parse_digest(path: Path) -> ParsedDigest:
    raw = path.read_text(encoding="utf-8")
    date = path.stem
    title_m = _HEADER_RE.search(raw)
    title = title_m.group(1).strip() if title_m else f"Daily Digest — {date}"

    pipeline_meta: dict[str, str] = {}
    for line in raw.splitlines():
        m = re.match(r"^-\s+\*\*(.+?)\*\*\s*:\s*(.+)$", line.strip())
        if m:
            pipeline_meta[m.group(1).strip()] = m.group(2).strip()

    hook = _extract_block(raw, "HOOK")
    close = _extract_block(raw, "CLOSE")
    meta_raw = _extract_block(raw, "META")
    meta: dict[str, str] = {}
    if meta_raw:
        for m in _META_LINE.finditer(meta_raw):
            meta[m.group(1)] = m.group(2).strip()

    items: list[DigestItem] = []
    parts = _ITEM_SPLIT.split(raw)
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            idx = int(parts[i])
            body = re.split(r"【(?:ITEM\d+|CLOSE|HOOK|META)】", parts[i + 1])[0]
            item = DigestItem(index=idx)
            current_key = None
            buffers: dict[str, list[str]] = {
                "标题": [],
                "类别": [],
                "原文摘录": [],
                "实用点": [],
                "来源": [],
            }
            for line in body.splitlines():
                fm = re.match(
                    r"^(标题|类别|原文摘录|实用点|来源)[：:]\s*(.*)$",
                    line,
                )
                if fm:
                    current_key = fm.group(1)
                    buffers[current_key].append(fm.group(2))
                elif current_key and line.strip() and not line.startswith("【"):
                    buffers[current_key].append(line.strip())
            item.title = " ".join(buffers["标题"]).strip()
            item.category = " ".join(buffers["类别"]).strip()
            item.quote = " ".join(buffers["原文摘录"]).strip()
            item.takeaway = " ".join(buffers["实用点"]).strip()
            item.source_raw = " ".join(buffers["来源"]).strip()
            item.handles = _HANDLE_RE.findall(item.source_raw)
            item.links = _URL_RE.findall(item.source_raw)
            if item.title or item.quote or item.takeaway:
                items.append(item)

    return ParsedDigest(
        date=date,
        title=title,
        pipeline_meta=pipeline_meta,
        hook=hook,
        meta=meta,
        items=items,
        close=close,
        structured=bool(hook or items),
        raw_md=raw,
    )


def md_fallback_html(md: str) -> str:
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
    return re.sub(
        r"(?:<li>.*?</li>\n?)+",
        lambda m: "<ul>\n" + m.group(0) + "</ul>\n",
        joined,
        flags=re.S,
    )


_CAT_CLASS = {
    "大佬官方": "tag-blue",
    "关注动态": "tag-violet",
    "工具更新": "tag-green",
    "行业趋势": "tag-amber",
    "中国相关": "tag-rose",
    "其他": "tag-zinc",
}


def cat_class(cat: str) -> str:
    for k, v in _CAT_CLASS.items():
        if k in cat:
            return v
    return "tag-zinc"


def signal_class(sig: str) -> str:
    if "强" in (sig or ""):
        return "sig-strong"
    if "弱" in (sig or ""):
        return "sig-weak"
    return "sig-mid"


def tweets_used(d: ParsedDigest) -> str:
    for k, v in d.pipeline_meta.items():
        if "tweet" in k.lower():
            return v
    return "—"


def blurb_from(d: ParsedDigest) -> str:
    if d.hook:
        return d.hook
    for line in d.raw_md.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("- **") or s == "---":
            continue
        if s.startswith("【") or s.startswith("_"):
            continue
        return s
    return "暂无摘要"


def shell(title: str, body: str, *, active: str = "home") -> str:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    home_cls = "active" if active == "home" else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="description" content="每日 X 精读 — twitter-cli + DeepSeek 自动策展"/>
  <meta name="theme-color" content="#0a0a0b"/>
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Serif:ital,wght@0,500;0,600;1,500&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="style.css?v={ASSET_VER}"/>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <a class="logo" href="index.html">
        <span class="logo-mark">X</span>
        <span class="logo-text">Daily Digest</span>
      </a>
      <nav class="topnav">
        <a class="{home_cls}" href="index.html">首页</a>
        <a href="https://github.com/DoTrungHuy/grok-daily-digest" target="_blank" rel="noopener">源码</a>
      </nav>
    </header>

    <main class="main">
{body}
    </main>

    <footer class="foot">
      <p>Cookie → DeepSeek → Pages · built {html.escape(gen)}</p>
      <p class="foot-links">
        <a href="https://dotrunghuy.github.io/grok-daily-digest/">站点</a>
        <span>·</span>
        <a href="https://github.com/DoTrungHuy/grok-daily-digest">GitHub</a>
      </p>
    </footer>
  </div>
  <script src="app.js?v={ASSET_VER}" defer></script>
</body>
</html>
"""


def render_item(item: DigestItem) -> str:
    cat = item.category or "其他"
    handles = " ".join(f'<span class="handle">{html.escape(h)}</span>' for h in item.handles[:3])
    links = "".join(
        f'<a class="src" href="{html.escape(u)}" target="_blank" rel="noopener">原文{i + 1}</a>'
        for i, u in enumerate(item.links[:4])
    )
    quote = (
        f'<blockquote class="quote"><p>{_inline(item.quote)}</p></blockquote>'
        if item.quote
        else ""
    )
    take = (
        f'<div class="take"><span class="take-k">实用点</span><p>{_inline(item.takeaway)}</p></div>'
        if item.takeaway
        else ""
    )
    return f"""
<article class="item" id="item-{item.index}" data-cat="{html.escape(cat)}">
  <div class="item-meta">
    <span class="item-idx">{item.index:02d}</span>
    <span class="tag {cat_class(cat)}">{html.escape(cat)}</span>
  </div>
  <h2 class="item-title">{html.escape(item.title or f"条目 {item.index}")}</h2>
  {quote}
  {take}
  <div class="item-src">
    {handles}
    <span class="src-links">{links}</span>
  </div>
</article>
"""


def render_digest_page(d: ParsedDigest) -> str:
    if not d.structured:
        return f"""
<div class="page-head">
  <a class="back" href="index.html">← 返回</a>
  <p class="eyebrow">Legacy · {html.escape(d.date)}</p>
  <h1 class="page-title">{html.escape(d.title)}</h1>
</div>
<article class="prose">{md_fallback_html(d.raw_md)}</article>
"""

    toc = "".join(
        f'<a href="#item-{it.index}" class="toc-a">'
        f'<span class="toc-i">{it.index:02d}</span>'
        f'<span class="toc-t">{html.escape(it.title or f"ITEM {it.index}")}</span></a>'
        for it in d.items
    )

    cats: list[str] = []
    seen: set[str] = set()
    for it in d.items:
        c = it.category or "其他"
        if c not in seen:
            seen.add(c)
            cats.append(c)
    filters = ""
    if len(cats) > 1:
        btns = ['<button type="button" class="fbtn on" data-f="*">全部</button>']
        for c in cats:
            btns.append(
                f'<button type="button" class="fbtn" data-f="{html.escape(c)}">{html.escape(c)}</button>'
            )
        filters = f'<div class="filters" role="toolbar">{"".join(btns)}</div>'

    items_html = "\n".join(render_item(it) for it in d.items)
    sig = d.meta.get("信号强度", "")
    close = ""
    if d.close:
        ct = re.sub(r"^一句话[：:]\s*", "", d.close).strip()
        close = f"""
<aside class="close-box">
  <p class="close-k">今日只看一条</p>
  <p class="close-v">{_inline(ct)}</p>
</aside>
"""

    meta_bits = []
    if d.meta.get("时间窗"):
        meta_bits.append(f'<span>{html.escape(d.meta["时间窗"])}</span>')
    meta_bits.append(f"<span>{len(d.items)} 条</span>")
    meta_bits.append(f"<span>{html.escape(tweets_used(d))} 推文</span>")
    if sig:
        meta_bits.append(
            f'<span class="sig {signal_class(sig)}">信号 {html.escape(sig)}</span>'
        )

    return f"""
<div class="digest-layout">
  <div class="digest-main">
    <div class="page-head">
      <a class="back" href="index.html">← 返回列表</a>
      <p class="eyebrow">Daily Digest · {html.escape(d.date)}</p>
      <h1 class="page-title">今日精读</h1>
      <p class="lede">{_inline(d.hook) if d.hook else html.escape(d.title)}</p>
      <div class="meta-row">{"".join(meta_bits)}</div>
    </div>

    {filters}
    <div class="items">
      {items_html}
    </div>
    {close}
  </div>

  <aside class="toc-side" aria-label="目录">
    <p class="toc-label">本篇目录</p>
    <nav class="toc">{toc}</nav>
  </aside>
</div>
"""


def render_index(digests: list[ParsedDigest]) -> str:
    latest = digests[0] if digests else None
    rows = []
    for i, d in enumerate(digests):
        blurb = blurb_from(d)
        n = len(d.items) if d.structured else "—"
        sig = d.meta.get("信号强度", "")
        kind = "结构化" if d.structured else "旧格式"
        is_latest = "is-latest" if i == 0 else ""
        rows.append(
            f"""
<a class="row {is_latest}" href="{html.escape(d.date)}.html">
  <div class="row-left">
    <time class="row-date" datetime="{html.escape(d.date)}">{html.escape(d.date)}</time>
    <span class="row-kind">{kind}</span>
  </div>
  <div class="row-body">
    <h2 class="row-title">{"今日精读" if i == 0 else html.escape(d.date)}</h2>
    <p class="row-blurb">{html.escape(blurb[:180])}{"…" if len(blurb) > 180 else ""}</p>
  </div>
  <div class="row-right">
    <span class="row-n">{n}<small>条</small></span>
    {f'<span class="sig {signal_class(sig)}">{html.escape(sig)}</span>' if sig else ""}
    <span class="row-arrow" aria-hidden="true">→</span>
  </div>
</a>
"""
        )

    hero = ""
    if latest:
        hero = f"""
<section class="hero">
  <p class="eyebrow">最新一期 · {html.escape(latest.date)}</p>
  <h1 class="hero-title">每日 X 精读</h1>
  <p class="lede">{html.escape(blurb_from(latest)[:280])}{"…" if len(blurb_from(latest)) > 280 else ""}</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="{html.escape(latest.date)}.html">阅读最新</a>
    <a class="btn btn-quiet" href="https://github.com/DoTrungHuy/grok-daily-digest" target="_blank" rel="noopener">源码</a>
  </div>
  <ul class="facts">
    <li><strong>{len(digests)}</strong> 期归档</li>
    <li><strong>{len(latest.items) if latest.structured else "—"}</strong> 条今日</li>
    <li><strong>08:00</strong> 北京日更</li>
  </ul>
</section>
"""
    else:
        hero = """
<section class="hero">
  <h1 class="hero-title">每日 X 精读</h1>
  <p class="lede">流水线就绪后，这里会出现每日策展。</p>
</section>
"""

    return f"""
{hero}

<section class="archive">
  <div class="section-bar">
    <h2 class="section-title">往期</h2>
    <p class="section-hint">按日期 · 点进可读完整条目</p>
  </div>
  <div class="list">
    {chr(10).join(rows) if rows else '<p class="empty">暂无内容</p>'}
  </div>
</section>

<section class="how">
  <div class="section-bar">
    <h2 class="section-title">流水线</h2>
  </div>
  <ol class="steps">
    <li><span class="step-n">1</span><div><strong>抓取 X</strong><span>twitter-cli + Cookie</span></div></li>
    <li><span class="step-n">2</span><div><strong>DeepSeek 策展</strong><span>HOOK / ITEM / CLOSE</span></div></li>
    <li><span class="step-n">3</span><div><strong>GitHub Pages</strong><span>docs 自动发布</span></div></li>
  </ol>
</section>
"""


CSS = r"""
/* Editorial calm dark — Linear-like + newsletter reading */

:root {
  --bg: #0a0a0b;
  --bg-2: #111113;
  --bg-3: #18181b;
  --border: #27272a;
  --border-2: #3f3f46;
  --text: #fafafa;
  --text-2: #a1a1aa;
  --text-3: #71717a;
  --accent: #38bdf8;
  --accent-dim: rgba(56, 189, 248, 0.12);
  --green: #4ade80;
  --amber: #fbbf24;
  --violet: #a78bfa;
  --rose: #fb7185;
  --blue: #60a5fa;
  --radius: 12px;
  --font: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  --serif: "IBM Plex Serif", Georgia, serif;
  --max: 1080px;
  --read: 42rem;
}

*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.6;
  color: var(--text);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { color: #7dd3fc; }
strong { font-weight: 600; color: var(--text); }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .875em;
  background: var(--bg-3);
  border: 1px solid var(--border);
  padding: .1em .35em;
  border-radius: 6px;
}

.shell {
  width: min(100% - 2rem, var(--max));
  margin: 0 auto;
  padding-bottom: 3rem;
}

/* Top bar */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 3.5rem;
  margin: 0 0 2rem;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(10, 10, 11, 0.88);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.logo {
  display: flex;
  align-items: center;
  gap: .55rem;
  color: var(--text) !important;
  font-weight: 600;
  font-size: .95rem;
}
.logo:hover { color: var(--text) !important; opacity: .9; }
.logo-mark {
  width: 1.5rem; height: 1.5rem;
  border-radius: 6px;
  background: linear-gradient(135deg, #38bdf8, #818cf8);
  color: #0a0a0b;
  font-size: .75rem;
  font-weight: 700;
  display: grid;
  place-items: center;
}
.topnav { display: flex; gap: .25rem; }
.topnav a {
  color: var(--text-2);
  font-size: .875rem;
  font-weight: 500;
  padding: .4rem .7rem;
  border-radius: 8px;
}
.topnav a:hover,
.topnav a.active {
  color: var(--text);
  background: var(--bg-3);
}

/* Hero (index) */
.hero {
  padding: .5rem 0 2.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2rem;
  max-width: var(--read);
}
.eyebrow {
  margin: 0 0 .75rem;
  font-size: .8rem;
  font-weight: 500;
  color: var(--text-3);
  letter-spacing: .02em;
}
.hero-title, .page-title {
  margin: 0 0 1rem;
  font-family: var(--serif);
  font-weight: 600;
  font-size: clamp(2rem, 5vw, 2.75rem);
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--text);
}
.lede {
  margin: 0 0 1.5rem;
  color: var(--text-2);
  font-size: 1.05rem;
  line-height: 1.65;
  max-width: 38rem;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: .6rem;
  margin-bottom: 1.75rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: .55rem 1.05rem;
  border-radius: 9px;
  font-size: .9rem;
  font-weight: 600;
  border: 1px solid transparent;
}
.btn-primary {
  background: var(--text);
  color: var(--bg) !important;
}
.btn-primary:hover { background: #e4e4e7; color: var(--bg) !important; }
.btn-quiet {
  background: transparent;
  border-color: var(--border-2);
  color: var(--text-2) !important;
}
.btn-quiet:hover {
  border-color: var(--text-3);
  color: var(--text) !important;
  background: var(--bg-2);
}
.facts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  color: var(--text-3);
  font-size: .875rem;
}
.facts strong {
  display: block;
  font-size: 1.15rem;
  color: var(--text);
  font-weight: 600;
  margin-bottom: .1rem;
}
.facts li { min-width: 4.5rem; }

/* Archive list */
.section-bar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.section-title {
  margin: 0;
  font-size: .95rem;
  font-weight: 600;
  color: var(--text);
}
.section-hint {
  margin: 0;
  font-size: .8rem;
  color: var(--text-3);
}
.list {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg-2);
}
.row {
  display: grid;
  grid-template-columns: 7.5rem 1fr auto;
  gap: 1rem;
  align-items: start;
  padding: 1.05rem 1.15rem;
  border-bottom: 1px solid var(--border);
  color: inherit !important;
  transition: background .12s;
}
.row:last-child { border-bottom: none; }
.row:hover { background: var(--bg-3); color: inherit !important; }
.row.is-latest {
  background: linear-gradient(90deg, var(--accent-dim), transparent 55%);
}
.row-date {
  display: block;
  font-size: .85rem;
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.row-kind {
  display: inline-block;
  margin-top: .25rem;
  font-size: .7rem;
  color: var(--text-3);
}
.row-title {
  margin: 0 0 .35rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  font-family: var(--font);
}
.row-blurb {
  margin: 0;
  font-size: .875rem;
  color: var(--text-2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.row-right {
  display: flex;
  align-items: center;
  gap: .65rem;
  white-space: nowrap;
  padding-top: .15rem;
}
.row-n {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.row-n small {
  font-size: .7rem;
  font-weight: 500;
  color: var(--text-3);
  margin-left: .15rem;
}
.row-arrow {
  color: var(--text-3);
  font-size: .95rem;
  transition: transform .12s, color .12s;
}
.row:hover .row-arrow {
  color: var(--accent);
  transform: translateX(2px);
}

/* Signal */
.sig {
  font-size: .7rem;
  font-weight: 600;
  padding: .15rem .45rem;
  border-radius: 999px;
  border: 1px solid var(--border);
}
.sig-strong { color: var(--green); border-color: rgba(74, 222, 128, .35); background: rgba(74, 222, 128, .08); }
.sig-mid { color: var(--amber); border-color: rgba(251, 191, 36, .35); background: rgba(251, 191, 36, .08); }
.sig-weak { color: var(--text-3); }

/* How / steps */
.how { margin-top: 2.5rem; }
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: .75rem;
}
.steps li {
  display: flex;
  gap: .75rem;
  align-items: flex-start;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-2);
}
.step-n {
  width: 1.5rem; height: 1.5rem;
  border-radius: 999px;
  background: var(--bg-3);
  border: 1px solid var(--border-2);
  display: grid;
  place-items: center;
  font-size: .75rem;
  font-weight: 700;
  color: var(--text-2);
  flex-shrink: 0;
}
.steps strong { display: block; font-size: .9rem; margin-bottom: .15rem; }
.steps span { font-size: .8rem; color: var(--text-3); }

/* Digest page layout */
.digest-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 15rem;
  gap: 2.5rem;
  align-items: start;
}
.page-head {
  max-width: var(--read);
  margin-bottom: 1.75rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border);
}
.back {
  display: inline-block;
  margin-bottom: .85rem;
  font-size: .875rem;
  color: var(--text-3);
  font-weight: 500;
}
.back:hover { color: var(--text); }
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: .65rem 1rem;
  font-size: .85rem;
  color: var(--text-3);
}
.meta-row span {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
}

/* Filters */
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
  margin-bottom: 1.25rem;
}
.fbtn {
  font-family: var(--font);
  font-size: .8rem;
  font-weight: 500;
  color: var(--text-2);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: .35rem .8rem;
  cursor: pointer;
}
.fbtn:hover { border-color: var(--border-2); color: var(--text); }
.fbtn.on {
  background: var(--text);
  border-color: var(--text);
  color: var(--bg);
}

/* Items */
.items {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: var(--read);
}
.item {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border);
}
.item:first-child { padding-top: .25rem; }
.item.is-hidden { display: none; }
.item-meta {
  display: flex;
  align-items: center;
  gap: .55rem;
  margin-bottom: .55rem;
}
.item-idx {
  font-size: .8rem;
  font-weight: 700;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
  letter-spacing: .04em;
}
.tag {
  font-size: .7rem;
  font-weight: 600;
  padding: .18rem .5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
}
.tag-blue { color: var(--blue); border-color: rgba(96,165,250,.35); background: rgba(96,165,250,.1); }
.tag-violet { color: var(--violet); border-color: rgba(167,139,250,.35); background: rgba(167,139,250,.1); }
.tag-green { color: var(--green); border-color: rgba(74,222,128,.35); background: rgba(74,222,128,.1); }
.tag-amber { color: var(--amber); border-color: rgba(251,191,36,.35); background: rgba(251,191,36,.1); }
.tag-rose { color: var(--rose); border-color: rgba(251,113,133,.35); background: rgba(251,113,133,.1); }
.tag-zinc { color: var(--text-2); }

.item-title {
  margin: 0 0 .9rem;
  font-family: var(--serif);
  font-weight: 600;
  font-size: 1.25rem;
  line-height: 1.35;
  letter-spacing: -0.015em;
  color: var(--text);
}
.quote {
  margin: 0 0 1rem;
  padding: .85rem 1rem;
  border-left: 3px solid var(--border-2);
  background: var(--bg-2);
  border-radius: 0 8px 8px 0;
}
.quote p {
  margin: 0;
  font-size: .925rem;
  color: var(--text-2);
  font-style: italic;
  line-height: 1.6;
}
.take { margin-bottom: 1rem; }
.take-k {
  display: block;
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: .35rem;
}
.take p {
  margin: 0;
  font-size: .95rem;
  color: var(--text);
  line-height: 1.65;
}
.item-src {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .5rem;
  justify-content: space-between;
}
.handle {
  font-size: .8rem;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-dim);
  padding: .2rem .5rem;
  border-radius: 999px;
}
.src-links { display: flex; flex-wrap: wrap; gap: .35rem; }
.src {
  font-size: .78rem;
  font-weight: 600;
  color: var(--text-2) !important;
  border: 1px solid var(--border);
  padding: .2rem .55rem;
  border-radius: 999px;
}
.src:hover {
  color: var(--text) !important;
  border-color: var(--border-2);
}

/* Close */
.close-box {
  margin-top: 1.75rem;
  padding: 1.25rem 1.35rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-2);
  max-width: var(--read);
}
.close-k {
  margin: 0 0 .5rem;
  font-size: .75rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--text-3);
}
.close-v {
  margin: 0;
  font-family: var(--serif);
  font-size: 1.15rem;
  line-height: 1.45;
  color: var(--text);
}

/* TOC side */
.toc-side {
  position: sticky;
  top: 4.25rem;
  padding-top: .25rem;
}
.toc-label {
  margin: 0 0 .65rem;
  font-size: .75rem;
  font-weight: 600;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: .05em;
}
.toc {
  display: flex;
  flex-direction: column;
  gap: .15rem;
  max-height: calc(100vh - 6rem);
  overflow: auto;
  padding-right: .25rem;
}
.toc-a {
  display: grid;
  grid-template-columns: 1.6rem 1fr;
  gap: .4rem;
  padding: .4rem .45rem;
  border-radius: 8px;
  color: var(--text-2) !important;
  font-size: .8rem;
  line-height: 1.35;
}
.toc-a:hover {
  background: var(--bg-3);
  color: var(--text) !important;
}
.toc-i {
  color: var(--text-3);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.toc-t {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Legacy prose */
.prose {
  max-width: var(--read);
  color: var(--text-2);
}
.prose h1, .prose h2, .prose h3 { color: var(--text); }
.prose h1 { font-family: var(--serif); font-size: 1.75rem; }
.prose h2 {
  font-size: 1.1rem;
  margin-top: 1.75rem;
  padding-bottom: .35rem;
  border-bottom: 1px solid var(--border);
}
.prose ul { padding-left: 1.2rem; }
.prose hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }

/* Footer */
.foot {
  margin-top: 3rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: .5rem;
  font-size: .8rem;
  color: var(--text-3);
}
.foot p { margin: 0; }
.foot-links { display: flex; gap: .4rem; align-items: center; }
.foot a { color: var(--text-2); }
.foot a:hover { color: var(--text); }

.empty {
  padding: 2rem;
  text-align: center;
  color: var(--text-3);
}

@media (max-width: 900px) {
  .digest-layout { grid-template-columns: 1fr; }
  .toc-side { display: none; }
  .steps { grid-template-columns: 1fr; }
  .row {
    grid-template-columns: 1fr;
    gap: .45rem;
  }
  .row-right { justify-content: flex-start; }
}
"""

JS = r"""
(function () {
  "use strict";
  var bar = document.querySelector(".filters");
  if (!bar) return;
  bar.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".fbtn");
    if (!btn) return;
    var f = btn.getAttribute("data-f");
    bar.querySelectorAll(".fbtn").forEach(function (b) {
      b.classList.toggle("on", b === btn);
    });
    document.querySelectorAll(".item").forEach(function (el) {
      var cat = el.getAttribute("data-cat") || "";
      el.classList.toggle("is-hidden", !(f === "*" || cat === f));
    });
  });
})();
"""


def build_site() -> Path:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (DOCS / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    files = sorted(DIGESTS.glob("????-??-??.md"), reverse=True)
    digests = [parse_digest(f) for f in files]

    (DOCS / "index.html").write_text(
        shell("X Daily Digest · 每日 X 精读", render_index(digests), active="home"),
        encoding="utf-8",
    )
    for d in digests:
        (DOCS / f"{d.date}.html").write_text(
            shell(
                f"Digest {d.date} · X Daily Digest",
                render_digest_page(d),
                active="digest",
            ),
            encoding="utf-8",
        )
    return DOCS


if __name__ == "__main__":
    out = build_site()
    print(f"Built → {out} (v={ASSET_VER}, {len(list(DIGESTS.glob('????-??-??.md')))} digests)")
