"""Expose Gmail client helpers under legacy import path.

This package re-exports the implementations located in
:mod:`email_utils.gmail_client` so existing code importing from
``src.email.gmail_client`` continues to work.
"""

from email_utils.gmail_client.gmail_auth import GmailAuth
from email_utils.gmail_client.gmail_send import send_email
from email_utils.gmail_client.gmail_receive import (
    search_emails,
    get_email_body,
    get_email_attachments,
)

__all__ = [
    "GmailAuth",
    "send_email",
    "search_emails",
    "get_email_body",
    "get_email_attachments",
]
