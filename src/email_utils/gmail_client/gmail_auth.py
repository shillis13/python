from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailAuth:
    """Handle Gmail API OAuth2 authentication."""

    def __init__(self, credentials_path: Path, token_path: Path) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds: Optional[Credentials] = None

    def authenticate(self) -> Credentials:
        """Authenticate and return Gmail API credentials."""
        if self.creds and self.creds.valid:
            return self.creds

        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logging.debug("Refreshing Gmail token")
                self.creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(f"Missing credentials.json at {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                self.creds = flow.run_local_server(port=0)
            self.token_path.write_text(self.creds.to_json())
        return self.creds
