"""Compatibility wrappers for Gmail receiving utilities."""
from email_utils.gmail_client.gmail_receive import (
    search_emails,
    get_email_body,
    get_email_attachments,
    build,
)

__all__ = [
    "search_emails",
    "get_email_body",
    "get_email_attachments",
    "build",
]
