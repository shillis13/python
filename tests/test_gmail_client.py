import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import pytest

from src.email.gmail_client.gmail_auth import GmailAuth
from src.email.gmail_client.gmail_send import send_email
from src.email.gmail_client.gmail_receive import search_emails, get_email_body, get_email_attachments


class DummyCreds:
    valid = True


def dummy_build(service, version, credentials=None):
    mock_service = MagicMock()
    messages = mock_service.users.return_value.messages.return_value
    messages.send.return_value.execute.return_value = {"id": "123"}
    messages.list.return_value.execute.return_value = {"messages": [{"id": "1"}]}
    messages.get.return_value.execute.return_value = {
        "payload": {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": "SGVsbG8="}},
                {"filename": "a.txt", "body": {"attachmentId": "1"}},
            ]
        }
    }
    attachments = mock_service.users.return_value.messages.return_value.attachments
    attachments.return_value.get.return_value.execute.return_value = {"data": "SGVsbG8="}
    return mock_service


@patch("src.email.gmail_client.gmail_send.build", new=dummy_build)
def test_send_email():
    auth = GmailAuth(Path("creds"), Path("token"))
    auth.authenticate = MagicMock(return_value=DummyCreds())
    msg_id = send_email(auth, "a@b.com", "sub", "body", dry_run=False)
    assert msg_id == "123"


@patch("src.email.gmail_client.gmail_receive.build", new=dummy_build)
def test_search_and_body_and_attachments(tmp_path):
    auth = GmailAuth(Path("creds"), Path("token"))
    auth.authenticate = MagicMock(return_value=DummyCreds())
    msgs = search_emails(auth, "test")
    assert msgs == [{"id": "1"}]

    body = get_email_body(auth, "1")
    assert body == "Hello"

    files = get_email_attachments(auth, "1", download_dir=tmp_path)
    assert len(files) == 1
    assert files[0].exists()

