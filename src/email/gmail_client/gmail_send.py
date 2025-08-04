"""Compatibility wrapper for Gmail sending utilities."""
from email_utils.gmail_client.gmail_send import send_email, build  # re-export

__all__ = ["send_email", "build"]
