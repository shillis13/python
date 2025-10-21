from __future__ import annotations
import argparse
from pathlib import Path

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import log_info, setup_logging
from dev_utils.lib_dryrun import get_kwarg

from .gmail_auth import GmailAuth
from .gmail_send import send_email
from .gmail_receive import get_email_body, get_email_attachments, search_emails


CREDENTIALS = Path(__file__).parent / "credentials.json"
TOKEN = Path(__file__).parent / "token.json"

auth = GmailAuth(CREDENTIALS, TOKEN)


def add_cli_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="command")

    send_parser = subparsers.add_parser("send", help="Send an email")
    send_parser.add_argument("--to", required=True)
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--body", required=True)
    send_parser.add_argument("--attach", nargs="*")
    send_parser.add_argument("--dry-run", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search emails")
    search_parser.add_argument("--query", required=True)


register_arguments(add_cli_args)


def main() -> None:
    setup_logging()
    args, _ = parse_known_args()

    if args.command == "send":
        attachments = [Path(p) for p in args.attach] if args.attach else None
        msg_id = send_email(
            auth, args.to, args.subject, args.body, attachments, dry_run=args.dry_run
        )
        log_info(f"Message ID: {msg_id}")
    elif args.command == "search":
        results = search_emails(auth, args.query)
        for msg in results:
            log_info(msg.get("id"))
    else:
        parser = argparse.ArgumentParser()
        add_cli_args(parser)
        parser.print_help()


if __name__ == "__main__":
    main()
