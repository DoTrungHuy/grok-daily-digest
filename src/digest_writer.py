"""Write digests/YYYY-MM-DD.md and refresh digests/README.md index."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import digests_dir


def write_digest_md(
    date_slug: str,
    body: str,
    *,
    tweet_count: int,
    errors: list[str] | None = None,
) -> Path:
    path = digests_dir() / f"{date_slug}.md"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        f"# Daily Digest — {date_slug}",
        "",
        f"- **Generated at**: {now}",
        f"- **Pipeline**: twitter-cli (Cookie) → DeepSeek",
        f"- **Tweets used**: {tweet_count}",
        f"- **X API**: not used",
        "",
    ]
    if errors:
        lines.append(f"- **Fetch warnings**: {len(errors)}")
        lines.append("")
    lines.extend(["---", "", body.strip(), "", "---", ""])
    lines.append("_Source: X via free cookie CLI + DeepSeek. Hosted on GitHub Pages._")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    rebuild_index()
    return path


def rebuild_index() -> None:
    d = digests_dir()
    files = sorted(d.glob("????-??-??.md"), reverse=True)
    lines = ["# Digests", "", "Newest first.", ""]
    for f in files:
        lines.append(f"- [{f.stem}](./{f.name})")
    lines.append("")
    (d / "README.md").write_text("\n".join(lines), encoding="utf-8")
