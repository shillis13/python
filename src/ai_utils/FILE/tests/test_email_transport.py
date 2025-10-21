from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)  # noqa: E402

from transports import EmailTransport  # pylint: disable=wrong-import-position


def test_send_files():
    with patch("transports.smtplib.SMTP_SSL") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        transport = EmailTransport(
            smtp_server="smtp", smtp_port=465, username="u", password="p", to_addr="to"
        )
        test_file = os.path.join(os.path.dirname(__file__), "__init__.py")
        transport.send_files([test_file], subject="sub")
        instance.login.assert_called_with("u", "p")
        instance.send_message.assert_called()


def test_receive_files():
    with patch("transports.imaplib.IMAP4_SSL") as mock_imap:
        imap_instance = mock_imap.return_value.__enter__.return_value
        imap_instance.search.return_value = ("OK", [b"1"])
        imap_instance.fetch.return_value = ("OK", [(b"1", b"")])
        with patch("transports.BytesParser") as bp:
            msg = MagicMock()
            part = MagicMock()
            part.get_filename.return_value = "f.txt"
            part.get_content.return_value = b"hi"
            msg.iter_attachments.return_value = [part]
            bp.return_value.parsebytes.return_value = msg
            transport = EmailTransport(
                smtp_server="smtp",
                smtp_port=465,
                username="u",
                password="p",
                to_addr="to",
            )
            tmpdir = os.path.dirname(__file__)
            files = transport.receive_files("sub", tmpdir)
            assert os.path.join(tmpdir, "f.txt") in files
