from __future__ import annotations
import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

from googleapiclient.discovery import build

from dev_utils.lib_logging import log_debug
from dev_utils.lib_dryrun import dry_run_decorator

from .gmail_auth import GmailAuth


@dry_run_decorator()
def send_email(
    auth: GmailAuth,
    to: str,
    subject: str,
    body: str,
    attachments: Optional[Iterable[Path]] = None,
    dry_run: bool = False,
) -> str:
    """Send an email and return the Gmail message ID."""
    creds = auth.authenticate()
    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["To"] = to
    message["From"] = "me"
    message["Subject"] = subject
    message.set_content(body)

    if attachments:
        for filepath in attachments:
            path = Path(filepath)
            if not path.exists():
                continue
            mime_type, _ = mimetypes.guess_type(path)
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            with path.open("rb") as fp:
                message.add_attachment(
                    fp.read(), maintype=maintype, subtype=subtype, filename=path.name
                )
            log_debug(f"Attached file {path}")

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": encoded_message})
        .execute()
    )
    msg_id = sent.get("id", "")
    log_debug(f"Sent message ID: {msg_id}")
    return msg_id
