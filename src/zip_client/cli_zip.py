import argparse
from pathlib import Path

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import setup_logging

from .zip_encrypt import zip_contents


DEFAULT_PASSWORD = "hunter2"


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sources",
        nargs="*",
        default=["."],
        help="Files or directories to zip. Defaults to current directory.",
    )
    parser.add_argument(
        "--recursive", action="store_true", default=False, help="Zip recursively"
    )
    parser.add_argument("--password", help="Encryption password")
    parser.add_argument("--output-name", help="Override output archive name")
    parser.add_argument("--use-gitignore", action="store_true", help="Honor .gitignore rules")
    parser.add_argument("--piz", action="store_true", help="Rename .zip to .piz")
    parser.add_argument("--bash", action="store_true", help="Add ~/bin/bash to archive")
    parser.add_argument("--python", action="store_true", help="Add ~/bin/python to archive")
    parser.add_argument(
        "--powershell", action="store_true", help="Add ~/bin/WindowsPowerShell"
    )
    parser.add_argument("--ai", action="store_true", help="Add ~/ai to archive")


register_arguments(add_args)


def parse_args():
    args, _ = parse_known_args(description="Zip files or folders with encryption.")
    return args


def gather_sources(args) -> list[Path]:
    sources = [Path(s).expanduser() for s in args.sources]

    if args.bash:
        sources.append(Path.home() / "bin/bash")
    if args.python:
        sources.append(Path.home() / "bin/python")
    if args.powershell:
        sources.append(Path.home() / "bin/WindowsPowerShell")
    if args.ai:
        sources.append(Path.home() / "ai")
    return sources


def main():
    setup_logging()
    args = parse_args()
    sources = gather_sources(args)
    password = args.password or DEFAULT_PASSWORD
    zip_contents(
        sources,
        password=password,
        recursive=args.recursive,
        use_gitignore=args.use_gitignore,
        rename_to_piz=args.piz,
        output_name=args.output_name,
    )


if __name__ == "__main__":
    main()

