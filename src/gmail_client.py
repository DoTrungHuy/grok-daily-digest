"""Gmail API client (readonly) for fetching Grok Tasks emails."""

from __future__ import annotations

import base64
import os
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Default paths relative to project root
DEFAULT_CLIENT_SECRET = "grok_client_secret.json"
DEFAULT_TOKEN = "token.json"

# Search query for Grok Tasks digests (verified: Grok <noreply@x.ai>)
DEFAULT_QUERY = "from:x.ai newer_than:7d"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return project_root() / p


def get_gmail_service(
    client_secret_path: str | Path = DEFAULT_CLIENT_SECRET,
    token_path: str | Path = DEFAULT_TOKEN,
):
    """
    Build an authenticated Gmail API service.

    First run opens a browser for OAuth consent and writes token.json.
    Later runs refresh the token automatically when possible.
    """
    client_secret = resolve_path(client_secret_path)
    token_file = resolve_path(token_path)

    if not client_secret.is_file():
        raise FileNotFoundError(
            f"找不到 OAuth 客户端文件: {client_secret}\n"
            f"请把 Google 下载的 JSON 放到项目根目录，默认名: {DEFAULT_CLIENT_SECRET}"
        )

    creds: Optional[Credentials] = None
    if token_file.is_file():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
            # offline + consent ensures refresh_token for later GitHub Actions use
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_body_data(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def extract_html_from_payload(payload: dict[str, Any]) -> str:
    """Return concatenated text/html parts from a Gmail message payload."""
    if not payload:
        return ""

    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        p_mime = part.get("mimeType", "")
        p_body = part.get("body") or {}
        p_data = p_body.get("data")
        if p_mime == "text/html" and p_data:
            html_parts.append(_decode_body_data(p_data))
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)

    if html_parts:
        return "\n".join(html_parts)

    # single-part html message
    mime = payload.get("mimeType", "")
    data = (payload.get("body") or {}).get("data")
    if mime == "text/html" and data:
        return _decode_body_data(data)
    return ""


def extract_grok_chat_url(html_or_text: str) -> Optional[str]:
    """Extract first https://grok.com/chat/<uuid> link (Continue reading target)."""
    import re

    if not html_or_text:
        return None
    # prefer chat URLs; strip tracking junk after uuid
    m = re.search(
        r"https://grok\.com/chat/([0-9a-fA-F-]{20,})",
        html_or_text,
    )
    if not m:
        return None
    return f"https://grok.com/chat/{m.group(1)}"


def extract_text_from_payload(payload: dict[str, Any]) -> str:
    """Prefer text/plain; fall back to text/html; walk multipart trees."""
    if not payload:
        return ""

    mime = payload.get("mimeType", "")
    body = payload.get("body") or {}
    data = body.get("data")

    if mime == "text/plain" and data:
        return _decode_body_data(data)

    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        p_mime = part.get("mimeType", "")
        p_body = part.get("body") or {}
        p_data = p_body.get("data")
        if p_mime == "text/plain" and p_data:
            plain_parts.append(_decode_body_data(p_data))
        elif p_mime == "text/html" and p_data:
            html_parts.append(_decode_body_data(p_data))
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)

    if plain_parts:
        return _clean_email_text("\n".join(plain_parts))
    if html_parts:
        return _html_to_text("\n".join(html_parts))

    if data:
        return _clean_email_text(_decode_body_data(data))
    return ""


def _html_to_text(html: str) -> str:
    import html as html_lib
    import re

    text = html or ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return _clean_email_text(text)


def _clean_email_text(text: str) -> str:
    import re

    text = text.replace("\xa0", " ").replace("\r", "")
    # Drop common Grok/xAI email chrome
    text = re.sub(r"-->+", "", text)
    text = re.sub(r"(?im)^\s*.*?\bis ready\s*$", "", text)
    text = re.sub(r"(?im)^\s*Continue reading\b.*$", "", text)
    text = re.sub(r"(?im)^\s*Unsubscribe\b.*$", "", text)
    text = re.sub(r"(?im)^\s*©\s*\d{4}\s*X\.AI.*$", "", text)
    text = re.sub(r"(?im)自动查询高质量内容\s*is ready\s*", "", text)
    text = re.sub(r"(?m)^\s*-\s*\d+\s*$", "", text)  # stray list markers from email chrome
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _header_map(headers: list[dict[str, str]]) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in headers or []}


def fetch_latest_message(
    service,
    query: str = DEFAULT_QUERY,
    max_results: int = 10,
) -> Optional[dict[str, Any]]:
    """
    Return the newest matching message as a dict with id, subject, from, date, body.
    """
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    messages = result.get("messages") or []
    if not messages:
        return None

    msg_id = messages[0]["id"]
    message = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )

    payload = message.get("payload") or {}
    headers = _header_map(payload.get("headers") or [])
    html = extract_html_from_payload(payload)
    body = extract_text_from_payload(payload)
    chat_url = extract_grok_chat_url(html) or extract_grok_chat_url(body)

    date_raw = headers.get("date", "")
    date_iso = ""
    if date_raw:
        try:
            date_iso = parsedate_to_datetime(date_raw).isoformat()
        except (TypeError, ValueError, IndexError):
            date_iso = date_raw

    return {
        "id": msg_id,
        "thread_id": message.get("threadId"),
        "subject": headers.get("subject", "(no subject)"),
        "from": headers.get("from", ""),
        "date": date_raw,
        "date_iso": date_iso,
        "snippet": message.get("snippet", ""),
        "body": body,
        "email_preview": body,
        "html": html,
        "chat_url": chat_url,
        "query": query,
        "content_source": "email_preview",
    }


def env_query() -> str:
    return os.environ.get("GMAIL_QUERY", DEFAULT_QUERY).strip() or DEFAULT_QUERY
