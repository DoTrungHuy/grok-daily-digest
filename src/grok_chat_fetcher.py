"""
Fetch full Grok Task chat content via logged-in browser session (Playwright).

Grok Tasks emails only contain a truncated preview + Continue reading →
https://grok.com/chat/<id>. Full text requires an authenticated session.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .gmail_client import project_root, resolve_path

DEFAULT_AUTH_STATE = "grok_auth.json"


class GrokChatFetchError(RuntimeError):
    """Raised when full chat content cannot be retrieved."""


def auth_state_path(path: str | Path = DEFAULT_AUTH_STATE) -> Path:
    return resolve_path(path)


def auth_state_exists(path: str | Path = DEFAULT_AUTH_STATE) -> bool:
    p = auth_state_path(path)
    return p.is_file() and p.stat().st_size > 10


def login_and_save_state(
    path: str | Path = DEFAULT_AUTH_STATE,
    *,
    timeout_ms: int = 300_000,
) -> Path:
    """
    Open a visible browser for the user to sign into grok.com, then save storage state.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise GrokChatFetchError(
            "未安装 playwright。请执行: pip install playwright && playwright install chromium"
        ) from e

    out = auth_state_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("【只需这一次】登录 Grok，之后每天全自动，不用再登")
    print("=" * 60)
    print("1. 即将打开 Chromium 浏览器")
    print("2. 请用接收 gork-daily 邮件的同一个账号登录 grok.com")
    print("3. 登录成功、能看到 Grok 主界面后，回到本终端按 Enter")
    print("4. 会把登录 cookie 存到 grok_auth.json（本地，不上传 GitHub）")
    print("5. 以后 run_daily.py 会自动用这份登录态抓全文")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://grok.com/", wait_until="domcontentloaded", timeout=120_000)
        try:
            input("\n>>> 登录完成后，在这里按 Enter 保存（只需一次）… ")
        except EOFError:
            # non-interactive environments: wait a while then save whatever state exists
            print("非交互环境：等待页面后保存当前状态…")
            page.wait_for_timeout(min(timeout_ms, 180_000))
        context.storage_state(path=str(out))
        browser.close()

    if not auth_state_exists(out):
        raise GrokChatFetchError(f"未能写入登录态: {out}")
    print(f"\n已保存登录态: {out}")
    print("之后请直接运行: python scripts/run_daily.py --force")
    print("无需再登录，除非几周后 cookie 过期（再跑一次本脚本即可）。")
    return out


def fetch_chat_full_text(
    chat_url: str,
    *,
    auth_path: str | Path = DEFAULT_AUTH_STATE,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> dict[str, Any]:
    """
    Open grok.com/chat/<id> with saved session and return extracted full text.
    """
    if not chat_url or "grok.com/chat/" not in chat_url:
        raise GrokChatFetchError(f"无效的 chat URL: {chat_url!r}")

    if not auth_state_exists(auth_path):
        raise GrokChatFetchError(
            f"缺少 Grok 登录态文件: {auth_state_path(auth_path)}\n"
            f"请先运行: python scripts/grok_login.py"
        )

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise GrokChatFetchError(
            "未安装 playwright。请执行: pip install playwright && playwright install chromium"
        ) from e

    state = str(auth_state_path(auth_path))
    text = ""
    title = ""
    final_url = chat_url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=state)
        page = context.new_page()
        try:
            page.goto(chat_url, wait_until="domcontentloaded", timeout=timeout_ms)
            # SPA hydrate
            page.wait_for_timeout(4000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except PlaywrightTimeout:
                pass
            page.wait_for_timeout(2000)

            final_url = page.url
            title = page.title() or ""
            body_text = page.evaluate(
                """() => {
                  const deny = /sign in|sign up|this chat is private|request access/i;
                  const root = document.querySelector('main')
                    || document.querySelector('#__next')
                    || document.body;
                  const t = (root && root.innerText) ? root.innerText.trim() : '';
                  return t;
                }"""
            )
            text = (body_text or "").strip()
        finally:
            browser.close()

    if not text:
        raise GrokChatFetchError(f"页面无文本内容: {final_url}")

    lower = text.lower()
    if (
        "this chat is private" in lower
        or "sign in to request access" in lower
        or (lower.count("sign in") >= 1 and len(text) < 800 and "【ITEM" not in text)
    ):
        raise GrokChatFetchError(
            "会话未登录或无权限访问该 chat（页面提示 private / sign in）。\n"
            "请重新运行: python scripts/grok_login.py"
        )

    cleaned = _clean_chat_text(text)
    if len(cleaned) < 200:
        raise GrokChatFetchError(
            f"抓取文本过短（{len(cleaned)} 字），可能页面结构变化或未加载完成。\n"
            f"URL: {final_url}"
        )

    return {
        "chat_url": chat_url,
        "final_url": final_url,
        "page_title": title,
        "full_text": cleaned,
        "char_count": len(cleaned),
    }


def _clean_chat_text(text: str) -> str:
    text = text.replace("\r", "")
    # drop common chrome
    lines = []
    skip_re = re.compile(
        r"^(sign in|sign up|log in|cookie|privacy|terms|new chat|share|regenerate|"
        r"copy|continue|grok|home|settings|upgrade|super ?grok)\s*$",
        re.I,
    )
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if skip_re.match(s) and len(s) < 40:
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def enrich_message_with_full_chat(
    message: dict[str, Any],
    *,
    auth_path: str | Path = DEFAULT_AUTH_STATE,
    headless: bool = True,
) -> dict[str, Any]:
    """
    If message has chat_url, fetch full text and set message['body'] to full content.
    On failure, leave preview body and set content_source / full_fetch_error.
    """
    chat_url = message.get("chat_url")
    if not chat_url:
        message["content_source"] = "email_preview_no_chat_url"
        message["full_fetch_error"] = "邮件中未找到 grok.com/chat 链接"
        return message

    try:
        result = fetch_chat_full_text(chat_url, auth_path=auth_path, headless=headless)
        message["email_preview"] = message.get("email_preview") or message.get("body")
        message["body"] = result["full_text"]
        message["full_text"] = result["full_text"]
        message["content_source"] = "grok_chat_full"
        message["chat_fetch"] = {
            "final_url": result.get("final_url"),
            "page_title": result.get("page_title"),
            "char_count": result.get("char_count"),
        }
        message.pop("full_fetch_error", None)
    except GrokChatFetchError as e:
        message["content_source"] = "email_preview_fetch_failed"
        message["full_fetch_error"] = str(e)
    return message
