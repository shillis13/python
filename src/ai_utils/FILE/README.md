# FILE Email Transport

This directory contains utilities for transferring files using different
communication mechanisms. Transports are pluggable so multiple remote
endpoints can be configured in `config.yml`.

## Email Transport

`EmailTransport` uses the standard `smtplib` and `imaplib` modules to send
and receive attachments. Credentials can be provided via the configuration
file or by environment variables.

### Sending

```python
from FILE.liaison import send_via_endpoint
send_via_endpoint(["data.txt"], endpoint="default", subject="Upload")
```

### Receiving

```python
from FILE.liaison import receive_from_endpoint
files = receive_from_endpoint("Upload", endpoint="default")
```

### MacOS Options

On macOS, Python can interface with:

- **SMTP/IMAP servers** using `smtplib` and `imaplib` (works with Gmail,
  iCloud, etc.).
- **Apple Mail** via `osascript` to programmatically compose and send mails.
- **Gmail API** (`google-api-python-client`) for OAuth based access.
- **Local sendmail/msmtp** if configured on the system.

Attachments may be added directly or encoded with base64 when embedding into
mail bodies. Incoming messages can be searched by subject to download
attachments to the local repository.
