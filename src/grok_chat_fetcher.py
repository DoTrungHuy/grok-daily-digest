"""
Fetch full Grok Task chat via persistent browser profile + saved session.

Login once (system Chrome/Edge + user-data-dir), complete Google/xAI OAuth,
then daily runs reuse the profile to open email's grok.com/chat URL.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

from .gmail_client import project_root, resolve_path

DEFAULT_AUTH_STATE = "grok_auth.json"
DEFAULT_PROFILE_DIR = "grok_browser_profile"
DEFAULT_CDP_PORT = 9222


class GrokChatFetchError(RuntimeError):
    pass


def auth_state_path(path: str | Path = DEFAULT_AUTH_STATE) -> Path:
    return resolve_path(path)


def profile_dir_path(path: str | Path = DEFAULT_PROFILE_DIR) -> Path:
    return resolve_path(path)


def auth_state_exists(path: str | Path = DEFAULT_AUTH_STATE) -> bool:
    p = auth_state_path(path)
    if p.is_file() and p.stat().st_size > 50:
        return True
    prof = profile_dir_path()
    return prof.is_dir() and any(prof.iterdir())


def _playwright():
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError as e:
        raise GrokChatFetchError(
            "未安装 playwright。\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium"
        ) from e


def _find_system_browser() -> Optional[Path]:
    candidates = [
        os.environ.get("CHROME_PATH"),
        os.environ.get("EDGE_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    for name in ("chrome", "msedge", "chrome.exe", "msedge.exe"):
        w = shutil.which(name)
        if w:
            return Path(w)
    return None


def _page_snapshot(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const t = (document.body && document.body.innerText || '');
          const lower = t.toLowerCase();
          const url = location.href;
          return {
            url,
            len: t.length,
            host: location.hostname,
            hasItem: t.includes('【ITEM') || /ITEM\\s*1/.test(t),
            hasHook: t.includes('【HOOK'),
            private: /this chat is private|sign in to request access/i.test(lower),
            cf: /just a moment|security verification|ray id/i.test(lower),
            googleAuth: /accounts\\.google\\.com|accounts\\.x\\.ai/.test(url),
            hasComposer: !!(document.querySelector('textarea')
              || document.querySelector('[contenteditable="true"]')),
            textSample: t.slice(0, 200)
          };
        }"""
    )


def _session_cookies_ok(context) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    # any auth-ish cookie on grok / x.ai domains
    for c in cookies:
        dom = (c.get("domain") or "").lower()
        name = (c.get("name") or "").lower()
        if not any(x in dom for x in ("grok.com", "x.ai", "x.com")):
            continue
        if any(k in name for k in ("session", "auth", "token", "sid", "jwt", "csrf")):
            return True
        # long-lived cookie values often indicate session
        if len(c.get("value") or "") > 20:
            return True
    return len(cookies) >= 5


def login_and_save_state(
    path: str | Path = DEFAULT_AUTH_STATE,
    *,
    timeout_ms: int = 900_000,
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
    cdp_port: int = DEFAULT_CDP_PORT,
    verify_chat_url: Optional[str] = None,
) -> Path:
    """
    Open system Chrome/Edge and KEEP IT OPEN until real login succeeds.

    Success = on grok.com chat page with digest markers (【HOOK】/【ITEM】)
    or substantial chat text — NOT just landing on grok.com homepage.
    Does NOT close the browser on false-positive homepage detection.
    """
    from playwright.sync_api import Error as PlaywrightError

    sync_playwright = _playwright()
    out = auth_state_path(path)
    prof = profile_dir_path(profile_dir)
    prof.mkdir(parents=True, exist_ok=True)

    if not verify_chat_url:
        try:
            from .gmail_client import fetch_latest_message, get_gmail_service

            msg = fetch_latest_message(get_gmail_service())
            if msg and msg.get("chat_url"):
                verify_chat_url = msg["chat_url"]
        except Exception:
            verify_chat_url = None
    target = verify_chat_url or "https://grok.com/chat"

    browser_exe = _find_system_browser()
    print("=" * 60)
    print("【登录一次】浏览器会一直开着，请慢慢登，不要急")
    print("=" * 60)
    print(f"浏览器: {browser_exe or 'Chromium 回退'}")
    print(f"将打开对话页:\n  {target}")
    print()
    print("请你做的事：")
    print("  1. 在弹出的窗口里完成 Google / xAI 登录（含二次验证）")
    print("  2. 若有 Cloudflare，手动点验证")
    print("  3. 直到页面上能看到完整摘要（【HOOK】【ITEM】等）")
    print("  4. 脚本检测到正文后才会保存并关闭浏览器")
    print()
    print("脚本不会因为「打开了 grok.com 首页」就提前关浏览器。")
    print(f"最长等待 {timeout_ms // 60000} 分钟。")
    print("=" * 60)

    proc: Optional[subprocess.Popen] = None
    try:
        if browser_exe:
            proc = subprocess.Popen(
                [
                    str(browser_exe),
                    f"--remote-debugging-port={cdp_port}",
                    f"--user-data-dir={prof}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    target,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(3)
            with sync_playwright() as p:
                try:
                    browser = p.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{cdp_port}"
                    )
                except PlaywrightError as e:
                    raise GrokChatFetchError(
                        f"无法连接浏览器调试口 {cdp_port}: {e}\n"
                        "请关掉其他带 --remote-debugging-port=9222 的 Chrome 后重试。"
                    ) from e
                context = (
                    browser.contexts[0] if browser.contexts else browser.new_context()
                )
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(target, wait_until="domcontentloaded", timeout=90_000)
                except PlaywrightError:
                    pass

                ok = _wait_for_real_session(
                    page, context, timeout_ms=timeout_ms, require_digest=True
                )
                # Only save when we have a real session; still save cookies if timeout
                # but warn loudly
                try:
                    context.storage_state(path=str(out))
                except Exception as e:
                    print(f"保存会话时出错: {e}")
                if ok:
                    print(f"\n✓ 真正登录成功，会话已保存: {out}")
                else:
                    print(
                        f"\n✗ 超时仍未看到完整对话正文。\n"
                        f"  已尽量保存 cookie 到 {out}，但可能无效。\n"
                        f"  请再运行本脚本，并确保浏览器里能打开上述 chat 链接看到全文。"
                    )
                # Disconnect CDP without killing user's work mid-way if still open:
                # after save, close debug connection then stop the chrome we launched
                try:
                    browser.close()
                except Exception:
                    pass
        else:
            webbrowser.open(target)
            print("已用系统默认方式打开链接；另开 Playwright 窗口用于保存会话，请在该窗口登录。")
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(prof),
                    headless=False,
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target, wait_until="domcontentloaded", timeout=120_000)
                ok = _wait_for_real_session(
                    page, context, timeout_ms=timeout_ms, require_digest=True
                )
                context.storage_state(path=str(out))
                context.close()
                if ok:
                    print(f"\n✓ 会话已保存: {out}")
                else:
                    print(f"\n✗ 超时，会话可能不完整: {out}")
    finally:
        # Close only the Chrome we started — after wait finished
        if proc is not None and proc.poll() is None:
            print("正在关闭本次启动的浏览器进程…")
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()

    if not out.is_file():
        raise GrokChatFetchError("未能保存 grok_auth.json")
    return out


def _wait_for_real_session(
    page,
    context,
    *,
    timeout_ms: int,
    require_digest: bool = True,
) -> bool:
    """
    Patient wait. Do NOT treat grok.com homepage as success.
    Success only when digest markers or long chat body is visible on grok.com
    and we are not on Google OAuth / CF walls.
    """
    from playwright.sync_api import Error as PlaywrightError

    waited = 0
    step = 4000
    print("浏览器请保持打开。正在等待你完成登录（检测到完整正文才会继续）…")
    while waited < timeout_ms:
        try:
            if page.is_closed():
                print("浏览器页面被关闭了。若不是你故意关的，请重跑登录脚本。")
                return False
            snap = _page_snapshot(page)
            host = snap.get("host") or ""
            url = snap.get("url") or ""

            if snap.get("googleAuth"):
                if waited % 20000 < step:
                    print(f"  [{waited // 1000}s] 请在浏览器完成 Google/xAI 登录与授权…")
                    print(f"         当前: {url[:100]}")
            elif snap.get("cf"):
                if waited % 20000 < step:
                    print(f"  [{waited // 1000}s] 请在浏览器通过 Cloudflare 验证…")
            elif snap.get("private"):
                if waited % 20000 < step:
                    print(f"  [{waited // 1000}s] 仍显示 private，请确认已登录正确账号…")
            elif "grok.com" in host:
                digest_ok = bool(snap.get("hasItem") or snap.get("hasHook"))
                long_ok = snap.get("len", 0) > 3000 and "/chat" in url
                if digest_ok or long_ok:
                    print(
                        f"✓ 已看到对话正文（{snap.get('len')} 字）\n"
                        f"  {url}"
                    )
                    page.wait_for_timeout(2000)
                    return True
                if waited % 20000 < step:
                    print(
                        f"  [{waited // 1000}s] 已在 grok.com，但还没有完整摘要正文，"
                        f"请继续登录或等待页面加载…（当前 {snap.get('len')} 字）"
                    )
            else:
                if waited % 20000 < step:
                    print(f"  [{waited // 1000}s] 当前页面: {url[:120]}")
        except PlaywrightError as e:
            msg = str(e).lower()
            # Navigations during Google OAuth destroy the JS context — keep waiting
            if (
                "execution context was destroyed" in msg
                or "navigation" in msg
                or "target closed" in msg
                or "most likely because of a navigation" in msg
            ):
                if waited % 20000 < step:
                    print(
                        f"  [{waited // 1000}s] 页面正在跳转（登录流程正常），"
                        f"浏览器会保持打开，请继续操作…"
                    )
            else:
                if waited % 20000 < step:
                    print(f"  [{waited // 1000}s] 页面暂时异常（继续等待）: {e}")

        try:
            page.wait_for_timeout(step)
        except PlaywrightError as e:
            msg = str(e).lower()
            if "target closed" in msg or "has been closed" in msg:
                print("浏览器窗口已关闭。")
                return False
            # navigation during wait — continue
        waited += step

    print(f"已等待 {timeout_ms // 1000}s，仍未检测到完整对话正文。")
    return False


def _looks_like_challenge_or_login(text: str, url: str = "") -> str | None:
    lower = (text or "").lower()
    u = (url or "").lower()
    if "accounts.google.com" in u or "accounts.x.ai" in u:
        return "google_oauth"
    if "just a moment" in lower or "performing security verification" in lower:
        return "cloudflare_challenge"
    if "ray id:" in lower and "cloudflare" in lower:
        return "cloudflare_challenge"
    if "this chat is private" in lower or "sign in to request access" in lower:
        return "private_or_login"
    if "sign in" in lower and len(text) < 1200 and "【item" not in lower:
        return "login_page"
    return None


def fetch_chat_full_text(
    chat_url: str,
    *,
    auth_path: str | Path = DEFAULT_AUTH_STATE,
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
    headless: bool = False,
    timeout_ms: int = 120_000,
    expect_subject: Optional[str] = None,
) -> dict[str, Any]:
    """
    Fetch ONE specific chat by URL from today's email.

    Important: Grok Tasks creates a NEW conversation id every run.
    Never reuse yesterday's /chat/<uuid> — always pass the URL extracted
    from the current email's Continue reading link.
    """
    if not chat_url or not re.search(r"grok\.com/(?:chat|c)/", chat_url):
        raise GrokChatFetchError(f"无效 chat URL: {chat_url!r}")

    if not auth_state_exists(auth_path):
        raise GrokChatFetchError("请先运行: python scripts/grok_login.py")

    conv_id = None
    m = re.search(r"/(?:chat|c)/([0-9a-fA-F-]{20,})", chat_url)
    if m:
        conv_id = m.group(1)
        print(f"本次只抓取该对话（每日新 ID，勿复用旧链接）: {conv_id}")

    # Always prefer visible browser when using system profile (more reliable)
    attempts = [False] if not headless else [True, False]

    last_err = None
    for use_headless in attempts:
        try:
            result = _fetch_chat_once(
                chat_url,
                auth_path=auth_path,
                profile_dir=profile_dir,
                headless=use_headless,
                timeout_ms=timeout_ms,
                expect_subject=expect_subject,
            )
            reason = _looks_like_challenge_or_login(
                result["full_text"], result.get("final_url", "")
            )
            if reason and use_headless:
                print(f"无界面遇到 {reason}，改有界面重试…")
                last_err = reason
                continue
            if reason:
                raise GrokChatFetchError(
                    f"未能进入完整对话（{reason}）。\n"
                    "请运行 python scripts/grok_login.py 完成授权，\n"
                    "并确认能打开【今天邮件里】的 Continue reading 链接。"
                )
            return result
        except GrokChatFetchError as e:
            last_err = str(e)
            if use_headless:
                print(f"抓取失败，有界面重试: {e}")
                continue
            raise
    raise GrokChatFetchError(last_err or "抓取失败")


def _fetch_chat_once(
    chat_url: str,
    *,
    auth_path: str | Path,
    profile_dir: str | Path,
    headless: bool,
    timeout_ms: int,
    expect_subject: Optional[str] = None,
) -> dict[str, Any]:
    """
    Prefer system Chrome + same persistent profile as login (CDP).
    This matches the browser that successfully loaded full digest during login.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    sync_playwright = _playwright()
    state_file = auth_state_path(auth_path)
    prof = profile_dir_path(profile_dir)
    browser_exe = _find_system_browser()

    text = ""
    title = ""
    final_url = chat_url
    proc: Optional[subprocess.Popen] = None
    cdp_port = DEFAULT_CDP_PORT + 1  # avoid clash with a concurrent login

    with sync_playwright() as p:
        browser = None
        context = None
        page = None
        try:
            if browser_exe and prof.is_dir() and any(prof.iterdir()) and not headless:
                # Same path as successful login: real Chrome + profile + CDP
                print(f"使用系统 Chrome 打开指定对话:\n  {chat_url}")
                proc = subprocess.Popen(
                    [
                        str(browser_exe),
                        f"--remote-debugging-port={cdp_port}",
                        f"--user-data-dir={prof}",
                        "--no-first-run",
                        "--no-default-browser-check",
                        chat_url,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(3)
                browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(chat_url, wait_until="domcontentloaded", timeout=timeout_ms)
                except PlaywrightError:
                    pass
            elif state_file.is_file():
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(storage_state=str(state_file))
                page = context.new_page()
                page.goto(chat_url, wait_until="domcontentloaded", timeout=timeout_ms)
            elif prof.is_dir() and any(prof.iterdir()):
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(prof),
                    headless=headless,
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(chat_url, wait_until="domcontentloaded", timeout=timeout_ms)
            else:
                raise GrokChatFetchError("无登录 profile，请先 grok_login.py")

            page.wait_for_timeout(3000)

            for i in range(50):
                try:
                    snap = _page_snapshot(page)
                except PlaywrightError:
                    page.wait_for_timeout(2000)
                    continue
                final_url = snap.get("url") or final_url
                if snap.get("googleAuth"):
                    if headless and not proc:
                        raise GrokChatFetchError("需要 Google 登录")
                    if i % 5 == 0:
                        print("  请在浏览器完成登录/授权…")
                    page.wait_for_timeout(3000)
                    continue
                if snap.get("cf"):
                    if headless and not proc:
                        raise GrokChatFetchError("cloudflare_challenge")
                    if i % 5 == 0:
                        print("  请通过 Cloudflare 验证（浏览器保持打开）…")
                    page.wait_for_timeout(3000)
                    continue
                if snap.get("private"):
                    raise GrokChatFetchError("private_or_login")
                if snap.get("hasItem") or snap.get("hasHook") or snap.get("len", 0) > 2500:
                    break
                page.wait_for_timeout(1500)

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeout:
                pass
            page.wait_for_timeout(1000)

            final_url = page.url
            title = page.title() or ""
            text = page.evaluate(
                """() => {
                  const root = document.querySelector('main')
                    || document.querySelector('#__next')
                    || document.body;
                  return (root && root.innerText) ? root.innerText.trim() : '';
                }"""
            )
            text = (text or "").strip()
            try:
                context.storage_state(path=str(state_file))
            except Exception:
                pass
        except PlaywrightError as e:
            raise GrokChatFetchError(f"打开 chat 失败: {e}") from e
        finally:
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if context and proc is None:
                    context.close()
            except Exception:
                pass
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except Exception:
                    proc.kill()

    reason = _looks_like_challenge_or_login(text, final_url)
    if reason:
        raise GrokChatFetchError(f"{reason}: {final_url}")

    cleaned = _clean_chat_text(text)
    if len(cleaned) < 400 and "【ITEM" not in cleaned and "【HOOK" not in cleaned:
        raise GrokChatFetchError(
            f"文本过短或不含 digest（{len(cleaned)} 字）: {final_url}"
        )

    if _looks_like_wrong_page(cleaned):
        raise GrokChatFetchError(
            f"抓到的页面不像 Tasks digest（可能串对话）: {final_url}"
        )

    # Optional: subject keywords should appear if email subject known
    if expect_subject:
        # take significant tokens from subject
        tokens = [t for t in re.split(r"\W+", expect_subject) if len(t) >= 4]
        hits = sum(1 for t in tokens if t.lower() in cleaned.lower())
        if tokens and hits == 0 and "【HOOK" not in cleaned:
            raise GrokChatFetchError(
                f"对话内容与邮件主题不符（主题: {expect_subject!r}），拒绝写入。"
            )

    # Must be the same conversation id when URL contains uuid
    m_mail = re.search(r"([0-9a-fA-F-]{20,})", chat_url)
    m_final = re.search(r"/(?:chat|c)/([0-9a-fA-F-]{20,})", final_url)
    if m_mail and m_final and m_mail.group(1).lower() != m_final.group(1).lower():
        raise GrokChatFetchError(
            f"对话 ID 不一致：邮件 {m_mail.group(1)} vs 页面 {m_final.group(1)}"
        )

    return {
        "chat_url": chat_url,
        "final_url": final_url,
        "page_title": title,
        "full_text": cleaned,
        "char_count": len(cleaned),
    }


def _looks_like_wrong_page(text: str) -> bool:
    """True if content is clearly not a daily digest."""
    lower = (text or "").lower()
    if "new login to your xai account" in lower:
        return True
    if "we've noticed a new login" in lower:
        return True
    # digest from our prompt almost always has these; if missing and short → wrong
    has_struct = "【hook" in lower or "【item" in lower or "【meta" in lower
    if not has_struct and len(text) < 800:
        return True
    return False


def _clean_chat_text(text: str) -> str:
    text = text.replace("\r", "")
    lines = []
    skip_re = re.compile(
        r"^(sign in|sign up|log in|cookie|privacy|terms|new chat|share|regenerate|"
        r"copy|continue|grok|home|settings|upgrade|super ?grok|this chat is private)\s*$",
        re.I,
    )
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if skip_re.match(s) and len(s) < 48:
            continue
        lines.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def enrich_message_with_full_chat(
    message: dict[str, Any],
    *,
    auth_path: str | Path = DEFAULT_AUTH_STATE,
    headless: bool = False,
) -> dict[str, Any]:
    """
    Full text comes ONLY from message['chat_url'] on THIS email.
    Each gork-daily run → new conversation id in that day's mail.
    """
    chat_url = message.get("chat_url")
    if not chat_url:
        message["content_source"] = "email_preview_no_chat_url"
        message["full_fetch_error"] = (
            "该邮件没有 grok.com/chat 链接（不是 Tasks 摘要邮件，已跳过）"
        )
        return message

    print(
        f"绑定邮件 → 对话:\n"
        f"  Subject : {message.get('subject')}\n"
        f"  Message : {message.get('id')}\n"
        f"  Chat URL: {chat_url}"
    )
    try:
        result = fetch_chat_full_text(
            chat_url,
            auth_path=auth_path,
            headless=headless,
            expect_subject=message.get("subject"),
        )
        message["email_preview"] = message.get("email_preview") or message.get("body")
        message["body"] = result["full_text"]
        message["full_text"] = result["full_text"]
        message["content_source"] = "grok_chat_full"
        cid_m = re.search(r"/(?:chat|c)/([0-9a-fA-F-]{20,})", chat_url)
        message["chat_fetch"] = {
            "final_url": result.get("final_url"),
            "page_title": result.get("page_title"),
            "char_count": result.get("char_count"),
            "conversation_id": cid_m.group(1) if cid_m else None,
            "from_email_id": message.get("id"),
            "from_email_subject": message.get("subject"),
        }
        message.pop("full_fetch_error", None)
    except GrokChatFetchError as e:
        message["content_source"] = "email_preview_fetch_failed"
        message["full_fetch_error"] = str(e)
    return message
