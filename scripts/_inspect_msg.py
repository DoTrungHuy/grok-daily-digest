from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.gmail_client import get_gmail_service  # noqa: E402


def walk(part: dict, depth: int = 0) -> None:
    mime = part.get("mimeType")
    body = part.get("body") or {}
    data = body.get("data")
    size = body.get("size")
    att = body.get("attachmentId")
    pad = "  " * depth
    print(f"{pad}mime={mime} size={size} has_data={bool(data)} att={bool(att)}")
    if data:
        raw = base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")
        print(f"{pad}  text_len={len(raw)}")
        print(f"{pad}  preview={raw[:300]!r}")
        urls = re.findall(r"https?://[^\s\"'<>]+", raw)
        print(f"{pad}  urls={urls[:15]}")
        if "Continue" in raw or "continue" in raw.lower() or "grok" in raw.lower():
            # print more context around continue
            for m in re.finditer(r".{0,40}[Cc]ontinue.{0,80}", raw):
                print(f"{pad}  context={m.group()!r}")
    for child in part.get("parts") or []:
        walk(child, depth + 1)


def main() -> None:
    msg_id = sys.argv[1] if len(sys.argv) > 1 else "19f5520987145bc9"
    service = get_gmail_service()
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )
    print("id", msg_id)
    print("snippet", msg.get("snippet"))
    walk(msg.get("payload") or {})


if __name__ == "__main__":
    main()
