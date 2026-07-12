"""DeepSeek API (OpenAI-compatible) for full daily digest text."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .paths import project_root

DEFAULT_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _system_prompt() -> str:
    p = project_root() / "prompts" / "digest_system.md"
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return "你是科技策展人。根据给定推文写完整中文每日 digest，勿编造。"


def chat_complete(
    user_content: str,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_KEY")
    if not key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY（环境变量或 GitHub Secrets）。")

    url = base_url.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {e.code}: {detail[:800]}") from e

    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected DeepSeek response: {payload!r}") from e


def summarize_tweets(tweets_block: str, *, date_label: str = "") -> str:
    user = (
        f"日期：{date_label or '今天'}\n\n"
        f"以下是从 X 抓取的原始材料，请生成完整每日 digest：\n\n"
        f"{tweets_block}"
    )
    return chat_complete(user)
