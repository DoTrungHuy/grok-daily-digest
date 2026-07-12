"""Write digest markdown files under digests/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .gmail_client import project_root
from .parse_digest import parse_structured_body


def digests_dir() -> Path:
    d = project_root() / "digests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def raw_dir() -> Path:
    d = digests_dir() / "raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


def date_slug_from_message(message: dict[str, Any], fallback: Optional[datetime] = None) -> str:
    """Prefer email Date header day; else local today."""
    iso = message.get("date_iso") or ""
    if iso:
        try:
            cleaned = iso.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            return dt.astimezone().strftime("%Y-%m-%d")
        except ValueError:
            pass
    fb = fallback or datetime.now().astimezone()
    return fb.strftime("%Y-%m-%d")


def render_markdown(message: dict[str, Any], date_slug: str, parsed: dict[str, Any]) -> str:
    body = (message.get("body") or "").strip()
    if not body:
        body = (message.get("snippet") or "").strip() or "（邮件正文为空，仅有 snippet/未解析到 text）"

    source = message.get("content_source") or "email_preview"
    lines = [
        f"# Daily Digest — {date_slug}",
        "",
        f"- **Fetched at**: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        f"- **From**: {message.get('from', '')}",
        f"- **Subject**: {message.get('subject', '')}",
        f"- **Email date**: {message.get('date', '')}",
        f"- **Gmail message id**: `{message.get('id', '')}`",
        f"- **Search query**: `{message.get('query', '')}`",
        f"- **Content source**: `{source}`",
    ]
    if message.get("chat_url"):
        lines.append(
            f"- **完整正文（Grok 网页，每日新对话）**: {message['chat_url']}"
        )
        lines.append(
            "- **说明**: 邮件/CI 只有预览；点上方链接（需登录 Grok）可看当天 Tasks 全文"
        )
    if message.get("full_fetch_error"):
        lines.append(f"- **Full fetch error**: {message['full_fetch_error']}")
    lines.extend(["", "---", ""])

    if parsed.get("structured"):
        if parsed.get("hook"):
            lines.extend(["## Hook", "", parsed["hook"], ""])
        if parsed.get("items"):
            lines.extend(["## Items", ""])
            for item in parsed["items"]:
                title = item.get("title") or f"Item {item.get('index')}"
                lines.append(f"### {item.get('index')}. {title}")
                if item.get("quote"):
                    lines.append(f"- **原文摘录**: {item['quote']}")
                if item.get("takeaway"):
                    lines.append(f"- **实用点**: {item['takeaway']}")
                if item.get("source"):
                    lines.append(f"- **来源**: {item['source']}")
                if not any(item.get(k) for k in ("quote", "takeaway", "source")):
                    lines.append("")
                    lines.append(item.get("raw", ""))
                lines.append("")
        lines.extend(["---", "", "## Raw body", "", body, ""])
    else:
        lines.extend(["## Content", "", body, ""])

    # Always keep email teaser when full chat was merged
    preview = (message.get("email_preview") or "").strip()
    if preview and source.startswith("grok_chat"):
        lines.extend(["---", "", "## Email preview (truncated by Grok)", "", preview, ""])

    lines.extend(
        [
            "---",
            "",
            "_Archived by grok-daily-digest "
            f"(source={source})._",
            "",
        ]
    )
    return "\n".join(lines)


def write_digest(
    message: dict[str, Any],
    date_slug: Optional[str] = None,
    *,
    force: bool = False,
) -> tuple[Path, str]:
    """
    Write digests/YYYY-MM-DD.md and digests/raw/YYYY-MM-DD.json.
    Returns (path, status) where status is 'written' | 'skipped_same_id' | 'overwritten'.
    """
    slug = date_slug or date_slug_from_message(message)
    path = digests_dir() / f"{slug}.md"
    msg_id = message.get("id") or ""

    if path.is_file() and not force:
        existing = path.read_text(encoding="utf-8")
        if msg_id and f"`{msg_id}`" in existing:
            return path, "skipped_same_id"

    parsed = parse_structured_body(message.get("body") or "")
    status = "overwritten" if path.is_file() else "written"
    path.write_text(render_markdown(message, slug, parsed), encoding="utf-8")

    raw_path = raw_dir() / f"{slug}.json"
    raw_payload = {
        "id": message.get("id"),
        "thread_id": message.get("thread_id"),
        "from": message.get("from"),
        "subject": message.get("subject"),
        "date": message.get("date"),
        "date_iso": message.get("date_iso"),
        "snippet": message.get("snippet"),
        "query": message.get("query"),
        "body": message.get("body"),
        "email_preview": message.get("email_preview"),
        "chat_url": message.get("chat_url"),
        "content_source": message.get("content_source"),
        "full_fetch_error": message.get("full_fetch_error"),
        "chat_fetch": message.get("chat_fetch"),
        "parsed": parsed,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _rebuild_index()
    return path, status


def _rebuild_index() -> None:
    """Simple digests/README.md index of archived days."""
    d = digests_dir()
    files = sorted(d.glob("????-??-??.md"), reverse=True)
    lines = [
        "# Digests index",
        "",
        "Auto-generated. Newest first.",
        "",
    ]
    if not files:
        lines.append("_No digests yet._")
    else:
        for f in files:
            lines.append(f"- [{f.stem}](./{f.name})")
    lines.append("")
    (d / "README.md").write_text("\n".join(lines), encoding="utf-8")
