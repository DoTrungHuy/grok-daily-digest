#!/usr/bin/env python3
"""
Interactive login to grok.com and save Playwright storage state (cookies).

Usage:
  C:\\Python\\Python312\\python.exe scripts\\grok_login.py

Then run daily pipeline with full-chat fetch:
  C:\\Python\\Python312\\python.exe scripts\\run_daily.py --force
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.grok_chat_fetcher import GrokChatFetchError, login_and_save_state  # noqa: E402


def main() -> int:
    try:
        path = login_and_save_state()
    except GrokChatFetchError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"OK: {path}")
    print("下次抓全文会自动使用此登录态。过期后重新运行本脚本即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
