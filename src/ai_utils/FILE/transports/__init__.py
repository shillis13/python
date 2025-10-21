from __future__ import annotations

import os
import base64
import smtplib
import imaplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser


class Transport(ABC):
    """Abstract transport class used for sending and receiving files."""

    @abstractmethod
    def send_files(
        self, files: list[str], subject: str, body: str = "", **kwargs
    ) -> None:
        """Send a list of files."""

    @abstractmethod
    def receive_files(
        self, subject_filter: str, download_dir: str, **kwargs
    ) -> list[str]:
        """Retrieve files matching a subject filter and return paths to downloaded files."""


class EmailTransport(Transport):
    """Transport implementation that uses SMTP and IMAP."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        to_addr: str,
        imap_server: str | None = None,
        imap_port: int = 993,
        use_ssl: bool = True,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_addr = to_addr
        self.imap_server = imap_server or smtp_server
        self.imap_port = imap_port
        self.use_ssl = use_ssl

    def _smtp(self):
        if self.use_ssl:
            return smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
        smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
        smtp.starttls()
        return smtp

    def send_files(
        self, files: list[str], subject: str, body: str = "", embed: bool = False
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.username
        msg["To"] = self.to_addr
        msg["Subject"] = subject
        msg.set_content(body or "Sent from FILE")

        for path in files:
            with open(path, "rb") as f:
                data = f.read()
            if embed:
                b64 = base64.b64encode(data).decode()
                msg.add_attachment(
                    b64,
                    maintype="text",
                    subtype="plain",
                    filename=os.path.basename(path) + ".b64",
                )
            else:
                msg.add_attachment(
                    data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=os.path.basename(path),
                )

        with self._smtp() as smtp:
            smtp.login(self.username, self.password)
            smtp.send_message(msg)

    def receive_files(self, subject_filter: str, download_dir: str) -> list[str]:
        received: list[str] = []
        with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
            imap.login(self.username, self.password)
            imap.select("INBOX")
            typ, data = imap.search(None, f'SUBJECT "{subject_filter}"')
            if typ != "OK":
                return received
            for num in data[0].split():
                typ, msg_data = imap.fetch(num, "(RFC822)")
                if typ != "OK":
                    continue
                msg = BytesParser(policy=policy.default).parsebytes(msg_data[0][1])
                for part in msg.iter_attachments():
                    filename = part.get_filename()
                    if not filename:
                        continue
                    os.makedirs(download_dir, exist_ok=True)
                    file_path = os.path.join(download_dir, filename)
                    with open(file_path, "wb") as fp:
                        fp.write(part.get_content())
                    received.append(file_path)
        return received
