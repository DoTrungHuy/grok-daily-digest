"""
Fetch X/Twitter content without paid X API.

Uses twitter-cli (Agent-Reach stack) with cookie auth:
  TWITTER_AUTH_TOKEN + TWITTER_CT0
or browser cookie extraction when run locally.

Ref: https://github.com/Panniantong/Agent-Reach
     https://github.com/public-clis/twitter-cli
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from .paths import project_root, x_raw_dir


@dataclass
class TweetItem:
    id: str
    user: str
    text: str
    url: str
    created_at: str = ""
    likes: int | None = None
    reposts: int | None = None
    source: str = ""  # user_timeline | search | feed


def load_accounts_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else project_root() / "config" / "accounts.yaml"
    if not p.is_file():
        p = project_root() / "config" / "accounts.example.yaml"
    if not p.is_file():
        return {"accounts": [], "searches": [], "per_user_max": 8, "max_items_for_llm": 40}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def find_twitter_cli() -> Optional[str]:
    for name in ("twitter", "twitter-cli"):
        w = shutil.which(name)
        if w:
            return w
    # Windows: Python Scripts next to interpreter
    import sys

    scripts = Path(sys.executable).resolve().parent / "Scripts"
    for name in ("twitter.exe", "twitter-cli.exe", "twitter", "twitter-cli"):
        p = scripts / name
        if p.is_file():
            return str(p)
    return None


def _run_json(cmd: list[str], timeout: int = 120) -> Any:
    env = os.environ.copy()
    # Pass through cookie env if set
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(cmd)}\n{err[:800]}")
    out = (r.stdout or "").strip()
    if not out:
        return None
    # Some CLIs print logs before JSON — try last JSON object/array
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(f"no JSON in output: {out[:500]}")


def _normalize_tweet(obj: dict[str, Any], source: str) -> Optional[TweetItem]:
    if not isinstance(obj, dict):
        return None
    # common field variants across CLIs
    text = (
        obj.get("full_text")
        or obj.get("text")
        or obj.get("content")
        or obj.get("rawContent")
        or ""
    )
    if not text:
        return None
    tid = str(obj.get("id") or obj.get("id_str") or obj.get("tweet_id") or "")
    user = (
        obj.get("user_screen_name")
        or obj.get("screen_name")
        or (obj.get("user") or {}).get("screen_name")
        if isinstance(obj.get("user"), dict)
        else None
    ) or obj.get("username") or obj.get("user") or "unknown"
    if isinstance(user, dict):
        user = user.get("screen_name") or user.get("username") or "unknown"
    user = str(user).lstrip("@")
    url = obj.get("url") or obj.get("tweet_url") or ""
    if not url and tid and user != "unknown":
        url = f"https://x.com/{user}/status/{tid}"
    elif not url and tid:
        url = f"https://x.com/i/web/status/{tid}"
    likes = obj.get("favorite_count") or obj.get("likes") or obj.get("likeCount")
    reposts = obj.get("retweet_count") or obj.get("reposts") or obj.get("retweetCount")
    created = str(obj.get("created_at") or obj.get("date") or obj.get("time") or "")
    return TweetItem(
        id=tid or url,
        user=user,
        text=text.strip(),
        url=url,
        created_at=created,
        likes=int(likes) if likes is not None else None,
        reposts=int(reposts) if reposts is not None else None,
        source=source,
    )


def _extract_list(data: Any) -> list[dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("tweets", "data", "results", "items", "statuses"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        # single tweet
        if data.get("text") or data.get("full_text"):
            return [data]
    return []


def fetch_user_tweets(cli: str, handle: str, max_n: int = 8) -> list[TweetItem]:
    handle = handle.lstrip("@")
    # twitter-cli v current: user-posts
    candidates = [
        [cli, "user-posts", handle, "--max", str(max_n), "--json"],
        [cli, "user-posts", handle, "--json", "--max", str(max_n)],
        [cli, "user", handle, "--json", "--max", str(max_n)],
    ]
    last_err = None
    for cmd in candidates:
        try:
            data = _run_json(cmd)
            items = []
            for raw in _extract_list(data):
                t = _normalize_tweet(raw, source=f"user:{handle}")
                if t:
                    items.append(t)
            if items:
                return items
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return []


def fetch_search(cli: str, query: str, max_n: int = 15) -> list[TweetItem]:
    candidates = [
        [cli, "search", query, "-t", "Latest", "--max", str(max_n), "--json"],
        [cli, "search", query, "--json", "--max", str(max_n)],
        [cli, "search", query, "--json", "-n", str(max_n)],
    ]
    last_err = None
    for cmd in candidates:
        try:
            data = _run_json(cmd)
            items = []
            for raw in _extract_list(data):
                t = _normalize_tweet(raw, source=f"search:{query}")
                if t:
                    items.append(t)
            if items:
                return items
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return []


def fetch_following_feed(cli: str, max_n: int = 30) -> list[TweetItem]:
    candidates = [
        [cli, "feed", "-t", "following", "--max", str(max_n), "--json"],
        [cli, "feed", "--following", "--max", str(max_n), "--json"],
        [cli, "feed", "--json", "--max", str(max_n)],
    ]
    for cmd in candidates:
        try:
            data = _run_json(cmd)
            items = []
            for raw in _extract_list(data):
                t = _normalize_tweet(raw, source="feed")
                if t:
                    items.append(t)
            if items:
                return items
        except Exception:
            continue
    return []


def collect_tweets(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Collect tweets via twitter-cli. Raises if CLI missing or auth broken.
    """
    cfg = cfg or load_accounts_config()
    cli = find_twitter_cli()
    if not cli:
        raise RuntimeError(
            "未找到 twitter CLI。请安装 Agent-Reach 推荐的 twitter-cli：\n"
            "  pip install twitter-cli   # 或 pipx install twitter-cli\n"
            "并配置 Cookie：TWITTER_AUTH_TOKEN + TWITTER_CT0\n"
            "参考: https://github.com/Panniantong/Agent-Reach"
        )

    per_user = int(cfg.get("per_user_max") or 8)
    max_for_llm = int(cfg.get("max_items_for_llm") or 40)
    items: list[TweetItem] = []
    errors: list[str] = []

    # following feed first
    try:
        items.extend(fetch_following_feed(cli, max_n=min(30, max_for_llm)))
    except Exception as e:
        errors.append(f"feed: {e}")

    for acc in cfg.get("accounts") or []:
        handle = (acc.get("handle") if isinstance(acc, dict) else str(acc) or "").lstrip("@")
        if not handle:
            continue
        try:
            items.extend(fetch_user_tweets(cli, handle, max_n=per_user))
        except Exception as e:
            errors.append(f"@{handle}: {e}")

    for s in cfg.get("searches") or []:
        if isinstance(s, str):
            q, mx = s, 15
        else:
            q, mx = s.get("query", ""), int(s.get("max") or 15)
        if not q:
            continue
        try:
            items.extend(fetch_search(cli, q, max_n=mx))
        except Exception as e:
            errors.append(f"search {q!r}: {e}")

    # dedupe by id/url
    seen = set()
    unique: list[TweetItem] = []
    for t in items:
        key = t.id or t.url or t.text[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)

    unique = unique[:max_for_llm]
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cli": cli,
        "count": len(unique),
        "errors": errors,
        "tweets": [asdict(t) for t in unique],
    }
    return payload


def save_raw_tweets(payload: dict[str, Any], date_slug: str | None = None) -> Path:
    day = date_slug or datetime.now().astimezone().strftime("%Y-%m-%d")
    path = x_raw_dir() / f"{day}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def tweets_to_prompt_block(tweets: list[dict[str, Any]]) -> str:
    lines = []
    for i, t in enumerate(tweets, 1):
        lines.append(
            f"[{i}] @{t.get('user','')} | {t.get('created_at','')} | "
            f"likes={t.get('likes')} reposts={t.get('reposts')} | src={t.get('source')}\n"
            f"URL: {t.get('url')}\n"
            f"TEXT: {t.get('text')}\n"
        )
    return "\n".join(lines)
