#!/usr/bin/env python3
"""Build liquid-glass static site from digests/*.md → docs/ (GitHub Pages /docs).

Visual system adapted from web_beauty/liquidGlassAgency:
- Instrument Serif (headings) + Barlow (body)
- Dark luxury base + liquid-glass luminous borders (mask-composite)
- Content logic mapped to UI: HOOK hero · META chips · ITEM cards · CLOSE
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

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^#\s+(.+)$", re.M)
_ITEM_SPLIT = re.compile(r"【ITEM(\d+)】")
_FIELD = re.compile(
    r"^(标题|类别|原文摘录|实用点|来源)[：:]\s*(.*)$",
    re.M,
)
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
    """Extract text between 【TAG】 and next 【...】 or end."""
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
    # parts: [pre, idx1, body1, idx2, body2, ...]
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            idx = int(parts[i])
            body = parts[i + 1]
            # cut at next section markers if any leaked
            body = re.split(r"【(?:ITEM\d+|CLOSE|HOOK|META)】", body)[0]
            item = DigestItem(index=idx)
            # line-based field parse for multiline values
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

    structured = bool(hook or items)
    return ParsedDigest(
        date=date,
        title=title,
        pipeline_meta=pipeline_meta,
        hook=hook,
        meta=meta,
        items=items,
        close=close,
        structured=structured,
        raw_md=raw,
    )


def md_fallback_html(md: str) -> str:
    """Simple markdown → HTML for legacy unstructured digests."""
    lines = md.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("# "):
            out.append(f"<h1 class='legacy-h1'>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2 class='legacy-h2'>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3 class='legacy-h3'>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            out.append(f"<li>{_inline(line[2:].strip())}</li>")
        elif line.strip() == "---":
            out.append("<hr class='divider'/>")
        elif not line.strip():
            out.append("")
        else:
            out.append(f"<p>{_inline(line)}</p>")
    joined = "\n".join(out)
    joined = re.sub(
        r"(?:<li>.*?</li>\n?)+",
        lambda m: "<ul class='legacy-list'>\n" + m.group(0) + "</ul>\n",
        joined,
        flags=re.S,
    )
    return joined


# ---------------------------------------------------------------------------
# Category styling helpers
# ---------------------------------------------------------------------------

_CAT_CLASS = {
    "大佬官方": "cat-official",
    "关注动态": "cat-follow",
    "工具更新": "cat-tool",
    "行业趋势": "cat-trend",
    "中国相关": "cat-cn",
    "其他": "cat-other",
}


def cat_class(cat: str) -> str:
    for k, v in _CAT_CLASS.items():
        if k in cat:
            return v
    return "cat-other"


def signal_class(sig: str) -> str:
    s = (sig or "").lower()
    if "强" in s:
        return "sig-strong"
    if "弱" in s:
        return "sig-weak"
    return "sig-mid"


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------


def shell(
    title: str,
    body: str,
    *,
    active: str = "home",
    extra_head: str = "",
    body_class: str = "",
) -> str:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    nav_home = "is-active" if active == "home" else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="description" content="每日 X 精读 — twitter-cli + DeepSeek 自动策展"/>
  <meta name="theme-color" content="#05070b"/>
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="style.css"/>
  {extra_head}
</head>
<body class="{body_class}">
  <div class="bg-orbits" aria-hidden="true">
    <div class="orb orb-a"></div>
    <div class="orb orb-b"></div>
    <div class="orb orb-c"></div>
    <div class="grid-fade"></div>
  </div>

  <header class="nav-wrap">
    <div class="nav-inner liquid-glass">
      <a class="brand" href="index.html">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-text">X Daily Digest</span>
      </a>
      <nav class="nav-links" aria-label="主导航">
        <a class="{nav_home}" href="index.html">首页</a>
        <a href="https://github.com/DoTrungHuy/grok-daily-digest" target="_blank" rel="noopener">源码</a>
        <a class="nav-cta liquid-glass-strong" href="https://github.com/DoTrungHuy/grok-daily-digest" target="_blank" rel="noopener">
          Pipeline <span class="cta-arrow" aria-hidden="true">↗</span>
        </a>
      </nav>
    </div>
  </header>

  <main class="page">
{body}
  </main>

  <footer class="site-footer">
    <div class="footer-inner liquid-glass">
      <div class="footer-row">
        <p class="footer-copy">© {datetime.now(timezone.utc).year} X Daily Digest · free Cookie → DeepSeek → Pages</p>
        <p class="footer-gen">built {html.escape(gen)}</p>
      </div>
      <p class="footer-note">不使用付费 X API · 内容由 DeepSeek 根据抓取推文策展</p>
    </div>
  </footer>

  <script src="app.js" defer></script>
</body>
</html>
"""


def render_meta_chips(d: ParsedDigest) -> str:
    chips = []
    mapping = [
        ("时间窗", "window"),
        ("条目数", "count"),
        ("来自关注账号优先", "priority"),
        ("信号强度", "signal"),
    ]
    for key, kind in mapping:
        val = d.meta.get(key)
        if not val:
            continue
        extra = signal_class(val) if kind == "signal" else ""
        chips.append(
            f'<span class="chip chip-{kind} {extra}"><span class="chip-k">{html.escape(key)}</span>'
            f'<span class="chip-v">{html.escape(val)}</span></span>'
        )
    # pipeline extras
    tweets = d.pipeline_meta.get("Tweets used") or d.pipeline_meta.get("Tweets used".replace(" ", " "))
    if not tweets:
        for k, v in d.pipeline_meta.items():
            if "tweet" in k.lower() or "Tweet" in k:
                tweets = v
                break
    if tweets:
        chips.append(
            f'<span class="chip chip-tweets"><span class="chip-k">推文</span>'
            f'<span class="chip-v">{html.escape(tweets)}</span></span>'
        )
    if not chips:
        return ""
    return f'<div class="meta-chips reveal">{"".join(chips)}</div>'


def render_item_card(item: DigestItem) -> str:
    cat = item.category or "其他"
    cc = cat_class(cat)
    handles = " ".join(
        f'<span class="handle">{html.escape(h)}</span>' for h in item.handles[:3]
    ) or '<span class="handle muted">@source</span>'
    links = "".join(
        f'<a class="src-link" href="{html.escape(u)}" target="_blank" rel="noopener">原文 {i + 1}</a>'
        for i, u in enumerate(item.links[:4])
    )
    quote_html = (
        f'<blockquote class="item-quote"><p>{_inline(item.quote)}</p></blockquote>'
        if item.quote
        else ""
    )
    take_html = (
        f'<div class="item-takeaway"><span class="take-label">实用点</span>'
        f'<p>{_inline(item.takeaway)}</p></div>'
        if item.takeaway
        else ""
    )
    return f"""
<article class="item-card liquid-glass reveal" id="item-{item.index}" data-category="{html.escape(cat)}">
  <div class="item-head">
    <span class="item-num">ITEM {item.index:02d}</span>
    <span class="cat-badge {cc}">{html.escape(cat)}</span>
  </div>
  <h3 class="item-title">{html.escape(item.title or f"条目 {item.index}")}</h3>
  {quote_html}
  {take_html}
  <div class="item-foot">
    <div class="item-handles">{handles}</div>
    <div class="item-links">{links}</div>
  </div>
</article>
"""


def render_toc(items: list[DigestItem]) -> str:
    if not items:
        return ""
    lis = []
    for it in items:
        label = html.escape(it.title or f"ITEM {it.index}")
        cat = html.escape(it.category or "")
        lis.append(
            f'<li><a href="#item-{it.index}"><span class="toc-n">{it.index:02d}</span>'
            f'<span class="toc-t">{label}</span>'
            f'<span class="toc-c {cat_class(it.category)}">{cat}</span></a></li>'
        )
    return f"""
<nav class="toc liquid-glass reveal" aria-label="本篇目录">
  <div class="toc-head">
    <span class="section-badge">目录</span>
    <p class="toc-hint">跳转到条目</p>
  </div>
  <ol class="toc-list">
    {"".join(lis)}
  </ol>
</nav>
"""


def render_filter_bar(items: list[DigestItem]) -> str:
    cats = []
    seen = set()
    for it in items:
        c = it.category or "其他"
        if c not in seen:
            seen.add(c)
            cats.append(c)
    if len(cats) <= 1:
        return ""
    btns = ['<button type="button" class="filter-btn is-on" data-filter="*">全部</button>']
    for c in cats:
        btns.append(
            f'<button type="button" class="filter-btn" data-filter="{html.escape(c)}">'
            f"{html.escape(c)}</button>"
        )
    return f'<div class="filter-bar reveal" role="toolbar" aria-label="按类别筛选">{"".join(btns)}</div>'


def render_digest_page(d: ParsedDigest) -> str:
    if not d.structured:
        body_md = md_fallback_html(d.raw_md)
        return f"""
<section class="hero hero-digest">
  <div class="hero-inner">
    <a class="back-link reveal" href="index.html">← 返回列表</a>
    <span class="section-badge reveal">Legacy digest</span>
    <h1 class="hero-title reveal" data-blur>{html.escape(d.date)}</h1>
    <p class="hero-sub reveal">{html.escape(d.title)}</p>
  </div>
</section>
<article class="legacy-article liquid-glass reveal">
{body_md}
</article>
"""

    items_html = "\n".join(render_item_card(it) for it in d.items)
    close_block = ""
    if d.close:
        close_text = re.sub(r"^一句话[：:]\s*", "", d.close).strip()
        close_block = f"""
<section class="close-section reveal">
  <div class="close-card liquid-glass-strong">
    <span class="section-badge">今日只看一条</span>
    <p class="close-text">{_inline(close_text)}</p>
  </div>
</section>
"""

    n_items = len(d.items)
    sig = d.meta.get("信号强度", "")
    return f"""
<section class="hero hero-digest">
  <div class="hero-inner">
    <a class="back-link reveal" href="index.html">← 返回列表</a>
    <div class="hero-badges reveal">
      <span class="section-badge">Daily Digest</span>
      <span class="date-pill liquid-glass">{html.escape(d.date)}</span>
      {f'<span class="sig-pill {signal_class(sig)} liquid-glass">{html.escape("信号 " + sig)}</span>' if sig else ""}
    </div>
    <h1 class="hero-title reveal" data-blur>今日精读</h1>
    <p class="hero-lede reveal">{_inline(d.hook) if d.hook else html.escape(d.title)}</p>
    {render_meta_chips(d)}
    <div class="hero-stats reveal">
      <div class="stat"><span class="stat-n font-heading">{n_items}</span><span class="stat-l">条目</span></div>
      <div class="stat"><span class="stat-n font-heading">{html.escape(d.pipeline_meta.get("Tweets used", "—"))}</span><span class="stat-l">推文素材</span></div>
      <div class="stat"><span class="stat-n font-heading">AI</span><span class="stat-l">DeepSeek 策展</span></div>
    </div>
  </div>
</section>

{render_toc(d.items)}
{render_filter_bar(d.items)}

<section class="items-grid" id="items">
  {items_html if items_html else "<p class='empty'>本篇暂无结构化条目。</p>"}
</section>

{close_block}
"""


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


def render_index(digests: list[ParsedDigest]) -> str:
    cards = []
    for i, d in enumerate(digests):
        blurb = blurb_from(d)
        n = len(d.items) if d.structured else "—"
        sig = d.meta.get("信号强度", "")
        badge = "structured" if d.structured else "legacy"
        cats = []
        seen = set()
        for it in d.items:
            c = it.category or ""
            if c and c not in seen:
                seen.add(c)
                cats.append(c)
        cat_row = "".join(
            f'<span class="mini-cat {cat_class(c)}">{html.escape(c)}</span>' for c in cats[:4]
        )
        featured = "featured" if i == 0 else ""
        cards.append(
            f"""
<a class="digest-card liquid-glass reveal {featured}" href="{html.escape(d.date)}.html">
  <div class="dc-top">
    <span class="date-pill">{html.escape(d.date)}</span>
    <span class="badge-kind">{badge}</span>
  </div>
  <h2 class="dc-title font-heading">{html.escape(d.date if i else "今日精读")}</h2>
  <p class="dc-blurb">{html.escape(blurb[:220])}{"…" if len(blurb) > 220 else ""}</p>
  <div class="dc-meta">
    <span class="dc-stat"><strong>{n}</strong> 条目</span>
    {f'<span class="sig-pill {signal_class(sig)}">{html.escape(sig)}</span>' if sig else ""}
  </div>
  {f'<div class="dc-cats">{cat_row}</div>' if cat_row else ""}
  <span class="dc-go">阅读全文 <span aria-hidden="true">→</span></span>
</a>
"""
        )

    latest = digests[0] if digests else None
    hero_hook = blurb_from(latest) if latest else "流水线就绪后，这里会出现每日策展。"
    latest_date = latest.date if latest else "—"
    n_total = len(digests)

    return f"""
<section class="hero hero-home">
  <div class="hero-inner">
    <div class="hero-badges reveal">
      <span class="pill-new liquid-glass">
        <span class="pill-dot">New</span>
        <span>twitter-cli · DeepSeek · Pages</span>
      </span>
    </div>
    <h1 class="hero-title reveal" data-blur>每日 X 精读</h1>
    <p class="hero-sub reveal">免费 Cookie 读 X → DeepSeek 完整总结 → 自动发布。<br class="hide-sm"/>不使用付费 X API，GitHub Actions 定时更新。</p>
    <div class="hero-cta reveal">
      {f'<a class="btn liquid-glass-strong" href="{html.escape(latest_date)}.html">阅读最新 <span aria-hidden="true">↗</span></a>' if latest else ""}
      <a class="btn btn-ghost" href="https://github.com/DoTrungHuy/grok-daily-digest" target="_blank" rel="noopener">查看源码</a>
    </div>
    <div class="hero-stats reveal">
      <div class="stat"><span class="stat-n font-heading">{n_total}</span><span class="stat-l">期 digest</span></div>
      <div class="stat"><span class="stat-n font-heading">{html.escape(latest_date)}</span><span class="stat-l">最近更新</span></div>
      <div class="stat"><span class="stat-n font-heading">08:00</span><span class="stat-l">北京时间日更</span></div>
    </div>
    <div class="hook-preview liquid-glass reveal">
      <span class="section-badge">最新 HOOK</span>
      <p>{html.escape(hero_hook[:320])}{"…" if len(hero_hook) > 320 else ""}</p>
    </div>
  </div>
</section>

<section class="pipeline-strip reveal">
  <div class="pipe-step liquid-glass"><span class="pipe-n">01</span><span class="pipe-t">X Cookie 抓取</span></div>
  <div class="pipe-arrow" aria-hidden="true">→</div>
  <div class="pipe-step liquid-glass"><span class="pipe-n">02</span><span class="pipe-t">DeepSeek 策展</span></div>
  <div class="pipe-arrow" aria-hidden="true">→</div>
  <div class="pipe-step liquid-glass"><span class="pipe-n">03</span><span class="pipe-t">GitHub Pages</span></div>
</section>

<section class="list-section">
  <div class="section-head reveal">
    <span class="section-badge">Archive</span>
    <h2 class="section-title font-heading">往期精读</h2>
    <p class="section-sub">按日期归档 · 结构化条目可按类别阅读</p>
  </div>
  <div class="digest-grid">
    {chr(10).join(cards) if cards else "<p class='empty liquid-glass'>暂无内容，等待流水线首次运行。</p>"}
  </div>
</section>
"""


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------

CSS = r"""
/* X Daily Digest — liquid glass system (web_beauty / liquidGlassAgency) */

:root {
  --bg: #05070b;
  --bg-elevated: #0a0e14;
  --fg: #f4f7fb;
  --muted: rgba(255, 255, 255, 0.58);
  --faint: rgba(255, 255, 255, 0.38);
  --line: rgba(255, 255, 255, 0.12);
  --accent: #9ec5ff;
  --accent-2: #c4b5fd;
  --ok: #6ee7b7;
  --warn: #fcd34d;
  --hot: #f9a8d4;
  --radius: 1.25rem;
  --radius-pill: 9999px;
  --font-heading: "Instrument Serif", "Times New Roman", serif;
  --font-body: "Barlow", system-ui, sans-serif;
  --nav-h: 4.5rem;
  --max: 1080px;
  --glass-blur: 16px;
}

*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font-body);
  font-weight: 400;
  color: var(--fg);
  background: var(--bg);
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
a { color: var(--accent); text-decoration: none; transition: color .2s, opacity .2s; }
a:hover { color: #fff; }
img { max-width: 100%; }
strong { font-weight: 600; color: #fff; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .88em;
  background: rgba(255,255,255,.06);
  padding: .1em .35em;
  border-radius: 6px;
}

.font-heading { font-family: var(--font-heading); font-style: italic; font-weight: 400; }

/* ---- Ambient background ---- */
.bg-orbits {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: .45;
  will-change: transform;
}
.orb-a {
  width: 48vw; height: 48vw; max-width: 640px; max-height: 640px;
  top: -12%; left: -8%;
  background: radial-gradient(circle, rgba(90,140,255,.35), transparent 70%);
  animation: drift 22s ease-in-out infinite alternate;
}
.orb-b {
  width: 40vw; height: 40vw; max-width: 520px; max-height: 520px;
  top: 35%; right: -12%;
  background: radial-gradient(circle, rgba(180,140,255,.28), transparent 70%);
  animation: drift 28s ease-in-out infinite alternate-reverse;
}
.orb-c {
  width: 36vw; height: 36vw; max-width: 420px; max-height: 420px;
  bottom: -10%; left: 30%;
  background: radial-gradient(circle, rgba(80,200,180,.18), transparent 70%);
  animation: drift 24s ease-in-out infinite alternate;
}
.grid-fade {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to bottom, rgba(5,7,11,.3), rgba(5,7,11,.92) 70%, #05070b),
    linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px);
  background-size: 100% 100%, 64px 64px, 64px 64px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 20%, transparent 75%);
}
@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(4%, 6%) scale(1.08); }
}

/* ---- Liquid glass ---- */
.liquid-glass {
  background: rgba(255, 255, 255, 0.03);
  background-blend-mode: luminosity;
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: none;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08);
  position: relative;
  overflow: hidden;
}
.liquid-glass::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.2px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.45) 0%,
    rgba(255, 255, 255, 0.15) 20%,
    rgba(255, 255, 255, 0) 40%,
    rgba(255, 255, 255, 0) 60%,
    rgba(255, 255, 255, 0.12) 80%,
    rgba(255, 255, 255, 0.35) 100%
  );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  z-index: 1;
}
.liquid-glass-strong {
  background: rgba(255, 255, 255, 0.06);
  background-blend-mode: luminosity;
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  border: none;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.25),
    inset 0 1px 1px rgba(255, 255, 255, 0.14);
  position: relative;
  overflow: hidden;
}
.liquid-glass-strong::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.35px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.55) 0%,
    rgba(255, 255, 255, 0.2) 22%,
    rgba(255, 255, 255, 0) 42%,
    rgba(255, 255, 255, 0) 58%,
    rgba(255, 255, 255, 0.18) 78%,
    rgba(255, 255, 255, 0.48) 100%
  );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  z-index: 1;
}

/* children above glass rim */
.liquid-glass > *,
.liquid-glass-strong > * { position: relative; z-index: 2; }

/* ---- Nav ---- */
.nav-wrap {
  position: fixed;
  top: 1rem;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  justify-content: center;
  padding: 0 1rem;
  pointer-events: none;
}
.nav-inner {
  pointer-events: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  width: min(100%, var(--max));
  padding: .55rem .65rem .55rem 1rem;
  border-radius: var(--radius-pill);
}
.brand {
  display: flex;
  align-items: center;
  gap: .65rem;
  color: #fff;
  font-weight: 500;
  font-size: .95rem;
  letter-spacing: .01em;
}
.brand:hover { color: #fff; opacity: .9; }
.brand-mark {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 30%, #fff, transparent 40%),
    linear-gradient(135deg, #7aa7ff, #b794f6 55%, #67e8f9);
  box-shadow: 0 0 20px rgba(122, 167, 255, .45);
}
.nav-links {
  display: flex;
  align-items: center;
  gap: .15rem;
}
.nav-links a {
  color: rgba(255,255,255,.78);
  font-size: .875rem;
  font-weight: 500;
  padding: .45rem .85rem;
  border-radius: var(--radius-pill);
}
.nav-links a:hover,
.nav-links a.is-active { color: #fff; background: rgba(255,255,255,.06); }
.nav-cta {
  display: inline-flex !important;
  align-items: center;
  gap: .35rem;
  margin-left: .35rem;
  color: #fff !important;
  padding: .45rem 1rem !important;
}
.nav-cta:hover { color: #fff !important; background: rgba(255,255,255,.1) !important; }
.cta-arrow { font-size: .85em; opacity: .85; }

/* ---- Layout ---- */
.page {
  position: relative;
  z-index: 1;
  width: min(100% - 2rem, var(--max));
  margin: 0 auto;
  padding: calc(var(--nav-h) + 2rem) 0 4rem;
}

/* ---- Hero ---- */
.hero { margin-bottom: 2.5rem; }
.hero-inner { max-width: 46rem; }
.hero-home .hero-inner { max-width: 40rem; }
.hero-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .5rem;
  margin-bottom: 1.25rem;
}
.section-badge,
.date-pill,
.sig-pill,
.badge-kind,
.pill-new {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  border-radius: var(--radius-pill);
  font-size: .75rem;
  font-weight: 500;
  letter-spacing: .02em;
}
.section-badge {
  padding: .35rem .85rem;
  background: rgba(255,255,255,.05);
  border: 1px solid var(--line);
  color: rgba(255,255,255,.8);
}
.pill-new {
  padding: .25rem .75rem .25rem .25rem;
  color: rgba(255,255,255,.85);
}
.pill-dot {
  background: #fff;
  color: #0a0a0a;
  border-radius: var(--radius-pill);
  padding: .2rem .55rem;
  font-size: .7rem;
  font-weight: 600;
}
.date-pill {
  padding: .35rem .8rem;
  color: rgba(255,255,255,.85);
  background: rgba(255,255,255,.04);
}
.sig-pill {
  padding: .3rem .7rem;
  font-size: .72rem;
}
.sig-strong { color: var(--ok); background: rgba(110,231,183,.1); }
.sig-mid { color: var(--warn); background: rgba(252,211,77,.1); }
.sig-weak { color: var(--faint); background: rgba(255,255,255,.05); }

.hero-title {
  font-family: var(--font-heading);
  font-style: italic;
  font-weight: 400;
  font-size: clamp(2.75rem, 8vw, 4.75rem);
  line-height: .92;
  letter-spacing: -0.03em;
  margin: 0 0 1rem;
  color: #fff;
}
.hero-sub,
.hero-lede {
  margin: 0 0 1.5rem;
  font-weight: 300;
  font-size: clamp(.95rem, 2.2vw, 1.1rem);
  color: var(--muted);
  line-height: 1.55;
  max-width: 36rem;
}
.hero-lede { max-width: 42rem; color: rgba(255,255,255,.78); font-weight: 400; }
.back-link {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--muted);
  font-size: .875rem;
}
.back-link:hover { color: #fff; }

.hero-cta {
  display: flex;
  flex-wrap: wrap;
  gap: .65rem;
  margin-bottom: 2rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .7rem 1.25rem;
  border-radius: var(--radius-pill);
  font-size: .9rem;
  font-weight: 500;
  color: #fff;
  border: none;
  cursor: pointer;
}
.btn:hover { color: #fff; opacity: .95; }
.btn-ghost {
  background: transparent;
  border: 1px solid var(--line);
  color: rgba(255,255,255,.85);
}
.btn-ghost:hover { background: rgba(255,255,255,.05); color: #fff; }

.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.75rem 0 1.5rem;
  max-width: 28rem;
}
.stat { display: flex; flex-direction: column; gap: .15rem; }
.stat-n {
  font-size: clamp(1.35rem, 3vw, 1.85rem);
  line-height: 1.1;
  color: #fff;
  letter-spacing: -0.02em;
}
.stat-l { font-size: .75rem; color: var(--faint); font-weight: 400; }

.hook-preview {
  margin-top: 1.5rem;
  padding: 1.15rem 1.25rem;
  border-radius: var(--radius);
  max-width: 40rem;
}
.hook-preview p {
  margin: .65rem 0 0;
  font-weight: 300;
  color: rgba(255,255,255,.78);
  font-size: .95rem;
}

/* ---- Meta chips ---- */
.meta-chips {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin: 1rem 0 0;
}
.chip {
  display: inline-flex;
  flex-direction: column;
  gap: .1rem;
  padding: .55rem .85rem;
  border-radius: 14px;
  background: rgba(255,255,255,.04);
  border: 1px solid var(--line);
  min-width: 7rem;
}
.chip-k { font-size: .65rem; color: var(--faint); text-transform: none; letter-spacing: .02em; }
.chip-v { font-size: .82rem; color: rgba(255,255,255,.9); font-weight: 500; }
.chip-signal.sig-strong .chip-v { color: var(--ok); }
.chip-signal.sig-mid .chip-v { color: var(--warn); }

/* ---- Pipeline strip ---- */
.pipeline-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .65rem;
  margin: 0 0 3rem;
}
.pipe-step {
  display: flex;
  align-items: center;
  gap: .65rem;
  padding: .7rem 1rem;
  border-radius: var(--radius-pill);
  flex: 1 1 10rem;
}
.pipe-n {
  font-family: var(--font-heading);
  font-style: italic;
  font-size: 1.15rem;
  color: rgba(255,255,255,.45);
}
.pipe-t { font-size: .88rem; color: rgba(255,255,255,.85); font-weight: 500; }
.pipe-arrow { color: var(--faint); font-size: .9rem; }

/* ---- Section heads ---- */
.section-head { margin-bottom: 1.5rem; }
.section-title {
  margin: .65rem 0 .4rem;
  font-size: clamp(1.85rem, 4vw, 2.6rem);
  line-height: 1;
  letter-spacing: -0.02em;
  color: #fff;
}
.section-sub { margin: 0; color: var(--muted); font-weight: 300; font-size: .95rem; }

/* ---- Digest list cards ---- */
.digest-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}
@media (min-width: 720px) {
  .digest-grid { grid-template-columns: 1fr 1fr; }
  .digest-card.featured { grid-column: 1 / -1; }
}
.digest-card {
  display: block;
  padding: 1.25rem 1.35rem 1.15rem;
  border-radius: calc(var(--radius) + 4px);
  color: inherit;
  transition: transform .25s ease, background .25s ease;
}
.digest-card:hover {
  transform: translateY(-3px);
  background: rgba(255,255,255,.05);
  color: inherit;
}
.dc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: .75rem;
}
.badge-kind {
  padding: .25rem .6rem;
  font-size: .68rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--accent-2);
  background: rgba(196,181,253,.1);
  border: 1px solid rgba(196,181,253,.2);
}
.dc-title {
  margin: 0 0 .55rem;
  font-size: 1.75rem;
  line-height: 1.05;
  color: #fff;
}
.digest-card.featured .dc-title { font-size: clamp(1.85rem, 4vw, 2.4rem); }
.dc-blurb {
  margin: 0 0 1rem;
  color: var(--muted);
  font-weight: 300;
  font-size: .92rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  align-items: center;
  margin-bottom: .65rem;
}
.dc-stat { font-size: .8rem; color: var(--faint); }
.dc-stat strong { color: #fff; font-weight: 600; }
.dc-cats { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .85rem; }
.mini-cat {
  font-size: .68rem;
  padding: .2rem .5rem;
  border-radius: var(--radius-pill);
  background: rgba(255,255,255,.05);
  border: 1px solid var(--line);
  color: rgba(255,255,255,.7);
}
.dc-go {
  font-size: .85rem;
  font-weight: 500;
  color: var(--accent);
}

/* Category colors */
.cat-official, .mini-cat.cat-official { color: #93c5fd; border-color: rgba(147,197,253,.25); background: rgba(59,130,246,.1); }
.cat-follow, .mini-cat.cat-follow { color: #c4b5fd; border-color: rgba(196,181,253,.25); background: rgba(139,92,246,.1); }
.cat-tool, .mini-cat.cat-tool { color: #6ee7b7; border-color: rgba(110,231,183,.25); background: rgba(16,185,129,.1); }
.cat-trend, .mini-cat.cat-trend { color: #fcd34d; border-color: rgba(252,211,77,.25); background: rgba(245,158,11,.1); }
.cat-cn, .mini-cat.cat-cn { color: #f9a8d4; border-color: rgba(249,168,212,.25); background: rgba(236,72,153,.1); }
.cat-other, .mini-cat.cat-other { color: rgba(255,255,255,.7); }

/* ---- TOC ---- */
.toc {
  padding: 1.15rem 1.25rem;
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
}
.toc-head {
  display: flex;
  align-items: center;
  gap: .75rem;
  margin-bottom: .85rem;
}
.toc-hint { margin: 0; font-size: .8rem; color: var(--faint); }
.toc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: .35rem;
}
.toc-list a {
  display: grid;
  grid-template-columns: 2.2rem 1fr auto;
  gap: .65rem;
  align-items: baseline;
  padding: .55rem .65rem;
  border-radius: 12px;
  color: rgba(255,255,255,.82);
  font-size: .88rem;
}
.toc-list a:hover { background: rgba(255,255,255,.05); color: #fff; }
.toc-n {
  font-family: var(--font-heading);
  font-style: italic;
  color: var(--faint);
  font-size: .95rem;
}
.toc-t {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.toc-c {
  font-size: .68rem;
  padding: .15rem .45rem;
  border-radius: var(--radius-pill);
  white-space: nowrap;
}

/* ---- Filter ---- */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
  margin-bottom: 1.25rem;
}
.filter-btn {
  font-family: var(--font-body);
  font-size: .8rem;
  font-weight: 500;
  color: rgba(255,255,255,.7);
  background: rgba(255,255,255,.04);
  border: 1px solid var(--line);
  border-radius: var(--radius-pill);
  padding: .4rem .85rem;
  cursor: pointer;
  transition: background .2s, color .2s, border-color .2s;
}
.filter-btn:hover { color: #fff; border-color: rgba(255,255,255,.25); }
.filter-btn.is-on {
  color: #0a0a0a;
  background: #fff;
  border-color: #fff;
}

/* ---- Item cards ---- */
.items-grid {
  display: grid;
  gap: 1rem;
}
.item-card {
  padding: 1.35rem 1.4rem 1.2rem;
  border-radius: calc(var(--radius) + 2px);
  transition: transform .2s ease, background .2s;
}
.item-card:hover { background: rgba(255,255,255,.045); }
.item-card.is-hidden { display: none; }
.item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: .75rem;
  margin-bottom: .7rem;
}
.item-num {
  font-family: var(--font-heading);
  font-style: italic;
  font-size: 1rem;
  color: var(--faint);
  letter-spacing: .02em;
}
.cat-badge {
  font-size: .72rem;
  font-weight: 500;
  padding: .28rem .65rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
}
.item-title {
  margin: 0 0 1rem;
  font-family: var(--font-heading);
  font-style: italic;
  font-weight: 400;
  font-size: clamp(1.35rem, 3vw, 1.7rem);
  line-height: 1.2;
  letter-spacing: -0.015em;
  color: #fff;
}
.item-quote {
  margin: 0 0 1rem;
  padding: .9rem 1rem;
  border-left: 2px solid rgba(158,197,255,.45);
  background: rgba(0,0,0,.25);
  border-radius: 0 12px 12px 0;
}
.item-quote p {
  margin: 0;
  font-style: italic;
  font-weight: 300;
  font-size: .92rem;
  color: rgba(255,255,255,.72);
  line-height: 1.6;
}
.item-takeaway {
  margin-bottom: 1.1rem;
}
.take-label {
  display: inline-block;
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--accent-2);
  margin-bottom: .35rem;
}
.item-takeaway p {
  margin: 0;
  font-size: .95rem;
  color: rgba(255,255,255,.86);
  font-weight: 400;
}
.item-foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: .75rem;
  padding-top: .85rem;
  border-top: 1px solid rgba(255,255,255,.08);
}
.item-handles { display: flex; flex-wrap: wrap; gap: .4rem; }
.handle {
  font-size: .8rem;
  font-weight: 500;
  color: var(--accent);
  background: rgba(158,197,255,.08);
  padding: .25rem .55rem;
  border-radius: var(--radius-pill);
}
.handle.muted { color: var(--faint); }
.item-links { display: flex; flex-wrap: wrap; gap: .4rem; }
.src-link {
  font-size: .78rem;
  font-weight: 500;
  color: rgba(255,255,255,.75);
  padding: .28rem .65rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: rgba(255,255,255,.03);
}
.src-link:hover { color: #fff; border-color: rgba(255,255,255,.3); }

/* ---- Close ---- */
.close-section { margin-top: 2rem; }
.close-card {
  padding: 1.5rem 1.6rem;
  border-radius: calc(var(--radius) + 4px);
}
.close-text {
  margin: .85rem 0 0;
  font-family: var(--font-heading);
  font-style: italic;
  font-size: clamp(1.2rem, 2.8vw, 1.55rem);
  line-height: 1.35;
  color: #fff;
  max-width: 40rem;
}

/* ---- Legacy article ---- */
.legacy-article {
  padding: 1.5rem 1.6rem 2rem;
  border-radius: var(--radius);
}
.legacy-article h1, .legacy-h1 {
  font-family: var(--font-heading);
  font-style: italic;
  font-size: 1.8rem;
  margin: 0 0 1rem;
}
.legacy-article h2, .legacy-h2 {
  font-size: 1.15rem;
  margin: 1.5rem 0 .6rem;
  color: #fff;
  border-bottom: 1px solid var(--line);
  padding-bottom: .35rem;
}
.legacy-article p { color: rgba(255,255,255,.8); font-weight: 300; }
.legacy-list { padding-left: 1.2rem; color: rgba(255,255,255,.8); }
.legacy-list li { margin: .35rem 0; }
.divider { border: none; border-top: 1px solid var(--line); margin: 1.5rem 0; }

/* ---- Footer ---- */
.site-footer {
  position: relative;
  z-index: 1;
  width: min(100% - 2rem, var(--max));
  margin: 0 auto 2rem;
}
.footer-inner {
  padding: 1.15rem 1.35rem;
  border-radius: var(--radius);
}
.footer-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: .5rem;
}
.footer-copy, .footer-gen, .footer-note {
  margin: 0;
  font-size: .75rem;
  color: var(--faint);
}
.footer-note { margin-top: .45rem; }

.empty {
  padding: 2rem;
  text-align: center;
  color: var(--muted);
  border-radius: var(--radius);
}

/* ---- Reveal / blur-in ---- */
.reveal {
  opacity: 0;
  transform: translateY(18px);
  filter: blur(8px);
  transition:
    opacity .7s cubic-bezier(.22,1,.36,1),
    transform .7s cubic-bezier(.22,1,.36,1),
    filter .7s cubic-bezier(.22,1,.36,1);
}
.reveal.is-in {
  opacity: 1;
  transform: none;
  filter: none;
}
.reveal[data-stagger] { transition-delay: var(--d, 0ms); }

/* blur title words */
.hero-title .blur-word {
  display: inline-block;
  opacity: 0;
  filter: blur(10px);
  transform: translateY(28px);
  transition:
    opacity .55s cubic-bezier(.22,1,.36,1),
    filter .55s cubic-bezier(.22,1,.36,1),
    transform .55s cubic-bezier(.22,1,.36,1);
  transition-delay: var(--d, 0ms);
}
.hero-title.is-in .blur-word {
  opacity: 1;
  filter: none;
  transform: none;
}

.hide-sm { display: none; }
@media (min-width: 640px) {
  .hide-sm { display: inline; }
}

@media (max-width: 640px) {
  .nav-links a:not(.nav-cta) { display: none; }
  .hero-stats { grid-template-columns: 1fr 1fr 1fr; gap: .65rem; }
  .toc-list a { grid-template-columns: 2rem 1fr; }
  .toc-c { display: none; }
  .pipe-arrow { display: none; }
  .item-foot { flex-direction: column; align-items: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  .orb { animation: none; }
  .reveal, .hero-title .blur-word {
    opacity: 1 !important;
    filter: none !important;
    transform: none !important;
    transition: none !important;
  }
}
"""

JS = r"""
(function () {
  "use strict";

  // Blur-in titles: split into words
  document.querySelectorAll("[data-blur]").forEach(function (el) {
    var text = el.textContent.trim();
    if (!text) return;
    el.setAttribute("aria-label", text);
    el.innerHTML = text
      .split(/(\s+)/)
      .map(function (part, i) {
        if (/^\s+$/.test(part)) return part;
        return (
          '<span class="blur-word" style="--d:' +
          i * 70 +
          'ms">' +
          part +
          "</span>"
        );
      })
      .join("");
  });

  // Stagger reveal delays for sibling cards
  document.querySelectorAll(".items-grid, .digest-grid").forEach(function (grid) {
    Array.prototype.forEach.call(grid.children, function (child, i) {
      if (child.classList && child.classList.contains("reveal")) {
        child.style.setProperty("--d", Math.min(i * 70, 420) + "ms");
      }
    });
  });

  var reveals = document.querySelectorAll(".reveal, [data-blur]");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    reveals.forEach(function (el) {
      io.observe(el);
    });
  } else {
    reveals.forEach(function (el) {
      el.classList.add("is-in");
    });
  }

  // Category filter
  var bar = document.querySelector(".filter-bar");
  if (bar) {
    bar.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".filter-btn");
      if (!btn) return;
      var f = btn.getAttribute("data-filter");
      bar.querySelectorAll(".filter-btn").forEach(function (b) {
        b.classList.toggle("is-on", b === btn);
      });
      document.querySelectorAll(".item-card").forEach(function (card) {
        var cat = card.getAttribute("data-category") || "";
        var show = f === "*" || cat === f;
        card.classList.toggle("is-hidden", !show);
      });
    });
  }
})();
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_site() -> Path:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (DOCS / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")

    files = sorted(DIGESTS.glob("????-??-??.md"), reverse=True)
    digests = [parse_digest(f) for f in files]

    index_html = shell(
        "X Daily Digest · 每日 X 精读",
        render_index(digests),
        active="home",
        body_class="page-home",
    )
    (DOCS / "index.html").write_text(index_html, encoding="utf-8")

    for d in digests:
        page = shell(
            f"Digest {d.date} · X Daily Digest",
            render_digest_page(d),
            active="digest",
            body_class="page-digest",
        )
        (DOCS / f"{d.date}.html").write_text(page, encoding="utf-8")

    return DOCS


if __name__ == "__main__":
    out = build_site()
    print(f"Built site → {out}")
    print(f"  index + {len(list(DIGESTS.glob('????-??-??.md')))} digests")
