#!/usr/bin/env python3
"""
Daily pipeline:
  1) Gmail OAuth → latest Grok Tasks email (preview only by design)
  2) Extract https://grok.com/chat/<id> from email HTML
  3) Playwright + saved login → full chat text
  4) Write digests/YYYY-MM-DD.md

Setup once:
  pip install -r requirements.txt
  playwright install chromium
  python scripts/grok_login.py          # browser login, save grok_auth.json
  python scripts/run_daily.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gmail_client import (  # noqa: E402
    DEFAULT_CLIENT_SECRET,
    DEFAULT_TOKEN,
    env_query,
    fetch_latest_message,
    get_gmail_service,
)
from src.grok_chat_fetcher import (  # noqa: E402
    DEFAULT_AUTH_STATE,
    auth_state_exists,
    enrich_message_with_full_chat,
)
from src.write_digest import write_digest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Grok Tasks email + optional full chat, archive digest"
    )
    parser.add_argument("--client-secret", default=DEFAULT_CLIENT_SECRET)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--query", default=None)
    parser.add_argument("--print-only", action="store_true")
    parser.add_argument("--preview-chars", type=int, default=2000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--skip-full-chat",
        action="store_true",
        help="Only use email preview (no Playwright)",
    )
    parser.add_argument(
        "--full-chat",
        action="store_true",
        default=True,
        help="Fetch full text from grok.com/chat (default: on)",
    )
    parser.add_argument(
        "--no-full-chat",
        action="store_true",
        help="Alias of --skip-full-chat",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window when fetching chat (debug)",
    )
    parser.add_argument(
        "--auth-state",
        default=DEFAULT_AUTH_STATE,
        help=f"Playwright storage state path (default: {DEFAULT_AUTH_STATE})",
    )
    args = parser.parse_args()

    want_full = not (args.skip_full_chat or args.no_full_chat)
    query = args.query if args.query is not None else env_query()

    print("Connecting to Gmail API (readonly)...")
    try:
        service = get_gmail_service(
            client_secret_path=args.client_secret,
            token_path=args.token,
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Authorization / connection failed: {e}", file=sys.stderr)
        return 1

    print(f"Searching mail with query: {query!r}")
    message = fetch_latest_message(service, query=query)
    if not message:
        print("没有找到匹配的邮件。")
        return 2

    print("=== 匹配到邮件 ===")
    print(f"From   : {message.get('from')}")
    print(f"Subject: {message.get('subject')}")
    print(f"Date   : {message.get('date')}")
    print(f"Id     : {message.get('id')}")
    print(f"Chat   : {message.get('chat_url') or '(未在邮件中找到 grok.com/chat 链接)'}")

    preview = message.get("email_preview") or message.get("body") or ""
    print("--- email preview ---")
    print(preview[: args.preview_chars])
    if len(preview) > args.preview_chars:
        print(f"... ({len(preview) - args.preview_chars} more chars)")

    if want_full:
        if not auth_state_exists(args.auth_state):
            print(
                f"\n[!] 未找到 Grok 登录态 {args.auth_state}。\n"
                f"    请先运行: python scripts/grok_login.py\n"
                f"    本次将仅归档邮件预览。",
                file=sys.stderr,
            )
        else:
            print("\nFetching full chat via Playwright (logged-in)...")
            message = enrich_message_with_full_chat(
                message,
                auth_path=args.auth_state,
                headless=not args.headed,
            )
            src = message.get("content_source")
            print(f"Content source: {src}")
            if message.get("full_fetch_error"):
                print(f"[!] Full fetch failed: {message['full_fetch_error']}", file=sys.stderr)
            else:
                full = message.get("body") or ""
                print(f"Full text length: {len(full)} chars")
                print("--- full text preview ---")
                print(full[: args.preview_chars])
                if len(full) > args.preview_chars:
                    print(f"... ({len(full) - args.preview_chars} more chars)")

    if args.print_only:
        return 0 if message.get("content_source") == "grok_chat_full" or not want_full else 3

    path, status = write_digest(message, force=args.force)
    if status == "skipped_same_id":
        print(f"\n已存在相同邮件 id，跳过写入: {path}")
        print("如需用全文覆盖，请加: --force")
    elif status == "overwritten":
        print(f"\n已覆盖写入: {path}")
    else:
        print(f"\n已写入: {path}")
    print(f"原始备份: digests/raw/{path.stem}.json")
    print(f"内容来源: {message.get('content_source')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
