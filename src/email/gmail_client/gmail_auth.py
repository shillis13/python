"""Compatibility wrapper for Gmail authentication utilities."""
from email_utils.gmail_client.gmail_auth import GmailAuth  # re-export

__all__ = ["GmailAuth"]
