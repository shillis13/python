from __future__ import annotations
import base64
from datetime import datetime
from email import message_from_bytes
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from googleapiclient.discovery import build

from dev_utils.lib_logging import log_debug
from dev_utils.lib_progressBar import ProgressBarContext

from .gmail_auth import GmailAuth


def _build_service(auth: GmailAuth):
    creds = auth.authenticate()
    return build("gmail", "v1", credentials=creds)


def search_emails(auth: GmailAuth, query: str, since: Optional[datetime] = None) -> List[Dict]:
    """Search the inbox using Gmail query syntax."""
    service = _build_service(auth)
    if since:
        timestamp = int(since.timestamp())
        query = f"{query} after:{timestamp}"
    response = service.users().messages().list(userId="me", q=query).execute()
    messages = response.get("messages", [])
    log_debug(f"Found {len(messages)} messages for query '{query}'")
    return messages


def get_email_body(auth: GmailAuth, msg_id: str) -> str:
    """Return the plain text or HTML body of a message."""
    service = _build_service(auth)
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})
    body = _extract_body(payload)
    return body


def _extract_body(payload: Dict) -> str:
    if "parts" not in payload:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode()
        return ""
    for part in payload.get("parts", []):
        mime_type = part.get("mimeType", "")
        if mime_type in ("text/plain", "text/html"):
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode()
        if part.get("parts"):
            result = _extract_body(part)
            if result:
                return result
    return ""


def get_email_attachments(auth: GmailAuth, msg_id: str, download_dir: Path = Path("tmp")) -> List[Path]:
    """Download attachments for the specified message."""
    service = _build_service(auth)
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    parts = msg.get("payload", {}).get("parts", [])
    attachment_paths: List[Path] = []

    for part in parts:
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            data = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=attachment_id)
                .execute()
            )
            file_data = base64.urlsafe_b64decode(data["data"])
            download_dir.mkdir(parents=True, exist_ok=True)
            path = download_dir / filename
            with path.open("wb") as f:
                f.write(file_data)
            attachment_paths.append(path)
            log_debug(f"Downloaded attachment {path}")
    return attachment_paths
