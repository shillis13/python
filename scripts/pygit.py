#!/usr/bin/env python3
"""Unified git workflow helper with dry-run/apply semantics."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


# ---------------------------------------------------------------------------
# ANSI helpers


class Ansi:
    _CODES = {
        "reset": "\033[0m",
        "green": "\033[32m",
        "blue": "\033[34m",
        "yellow": "\033[33m",
        "red": "\033[31m",
    }

    @classmethod
    def colorize(cls, text: str, color: str, enabled: bool) -> str:
        if not enabled or color not in cls._CODES:
            return text
        return f"{cls._CODES[color]}{text}{cls._CODES['reset']}"


# ---------------------------------------------------------------------------
# Printing helpers


@dataclass
class Printer:
    apply: bool
    color_enabled: bool
    quiet: bool
    verbose: int = 0

    def _emit(self, message: str, color: Optional[str] = None) -> None:
        if self.quiet:
            return
        if color:
            message = Ansi.colorize(message, color, self.color_enabled)
        print(message)

    def action(self, message: str) -> None:
        color = "blue" if self.apply else "green"
        self._emit(message, color=color)

    def detail(self, message: str) -> None:
        if self.verbose > 0 and not self.quiet:
            self._emit(message)

    def warn(self, message: str) -> None:
        self._emit(message, color="yellow")

    def error(self, message: str) -> None:
        self._emit(message, color="red")


# ---------------------------------------------------------------------------
# Git helpers


class GitError(RuntimeError):
    pass


class GitRepo:
    def __init__(self, path: Path, printer: Printer) -> None:
        self.path = path
        self.printer = printer

    def run(self, *args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
        cmd = ["git", *args]
        kwargs = {
            "cwd": self.path,
            "text": True,
        }
        if capture:
            kwargs.update({"capture_output": True})
        else:
            kwargs.update({"stdout": None, "stderr": None})
        self.printer.detail(f"Running: {shlex.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=check, **kwargs)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or ""
            raise GitError(stderr.strip() or str(exc)) from exc
        return result

    def ensure_repo(self) -> None:
        try:
            self.run("rev-parse", "--is-inside-work-tree")
        except GitError as exc:
            raise GitError("Not a git repository") from exc

    def refresh_remotes(self) -> None:
        try:
            self.run("fetch", "--quiet")
        except GitError:
            # Ignore fetch failures in dry-run contexts; errors will surface later.
            self.printer.detail("git fetch --quiet failed (continuing without refresh)")

    def current_branch(self) -> str:
        result = self.run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def upstream(self) -> Optional[str]:
        try:
            result = self.run("rev-parse", "--abbrev-ref", "@{upstream}")
            return result.stdout.strip()
        except GitError:
            return None

    def ahead_behind(self) -> tuple[int, int]:
        upstream = self.upstream()
        if not upstream:
            return 0, 0
        try:
            result = self.run("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        except GitError:
            return 0, 0
        behind_s, ahead_s = result.stdout.strip().split()
        return int(ahead_s), int(behind_s)

    def working_tree_summary(self) -> dict[str, int]:
        result = self.run("status", "--porcelain")
        staged = unstaged = untracked = 0
        for line in result.stdout.splitlines():
            if not line:
                continue
            if line[0] != " " and line[0] != "?":
                staged += 1
            if line[0] == " " and line[1] != "?":
                unstaged += 1
            if line.startswith("??"):
                untracked += 1
        return {"staged": staged, "unstaged": unstaged, "untracked": untracked}

    def has_merges_ahead(self) -> bool:
        upstream = self.upstream()
        if not upstream:
            return False
        result = self.run("rev-list", "--merges", "@{upstream}..HEAD")
        return bool(result.stdout.strip())

    def ahead_files(self) -> tuple[Optional[List[str]], Optional[str]]:
        upstream = self.upstream()
        if not upstream:
            return None, "No upstream configured"
        if self.has_merges_ahead():
            return None, "Commits include merges; skipping file list"
        try:
            log = self.run("log", "@{upstream}..HEAD", "--name-status", "--pretty=format:")
        except GitError as exc:
            return None, str(exc)
        files: set[str] = set()
        for line in log.stdout.splitlines():
            if not line.strip():
                continue
            status, *rest = line.split("\t")
            status = status.strip()
            if status.startswith("R") or status.startswith("C"):
                return None, "Renames or copies detected; skipping file list"
            if rest:
                files.add(rest[-1])
        return sorted(files), None

    def staged_files(self) -> List[str]:
        result = self.run("diff", "--cached", "--name-only")
        return [line for line in result.stdout.splitlines() if line]

    def is_staged_clean(self) -> bool:
        try:
            self.run("diff", "--cached", "--quiet")
            return True
        except GitError:
            return False


# ---------------------------------------------------------------------------
# Command implementations


def cmd_status(repo: GitRepo, printer: Printer) -> int:
    repo.ensure_repo()
    branch = repo.current_branch()
    upstream = repo.upstream() or "(no upstream)"
    ahead, behind = repo.ahead_behind()
    wt = repo.working_tree_summary()
    printer.action(f"Branch: {branch}")
    printer.action(f"Upstream: {upstream}")
    printer.action(f"Ahead: {ahead} | Behind: {behind}")
    printer.action(
        "Working tree -> staged: {staged}, unstaged: {unstaged}, untracked: {untracked}".format(
            **wt
        )
    )
    if upstream == "(no upstream)":
        printer.warn("Set an upstream with: pygit set-upstream <remote> <branch>")
        return 2
    return 0


def cmd_pull(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    rebase = args.rebase
    if not printer.apply:
        printer.action("Would run: git fetch --prune")
        printer.action("Would run: git pull {}".format("--rebase" if rebase else ""))
        return 0
    repo.run("fetch", "--prune")
    pull_args = ["pull"]
    if rebase:
        pull_args.append("--rebase")
    repo.run(*pull_args)
    printer.action("Pull complete")
    return 0


def _print_ahead_files(repo: GitRepo, printer: Printer) -> None:
    files, reason = repo.ahead_files()
    if files is None:
        printer.warn(reason)
    elif not files:
        printer.action("No files to push")
    else:
        printer.action("Files to push:")
        for path in files:
            printer.action(f"  {path}")


def cmd_push(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    repo.refresh_remotes()
    upstream = repo.upstream()
    if not upstream:
        printer.error("No upstream configured. Use pygit set-upstream <remote> <branch>.")
        return 2
    ahead, behind = repo.ahead_behind()
    if behind > 0:
        printer.error("Cannot push: branch is behind upstream.")
        printer.warn("Run 'pygit pull --rebase' or 'pygit sync' first.")
        return 2
    if not printer.apply:
        printer.action("Would run: git add -A")
        if args.message:
            printer.action(f"Would run: git commit -m {args.message!r}")
        else:
            printer.action("Would create commit if staged changes exist")
        printer.action("Would run: git push")
        _print_ahead_files(repo, printer)
        return 0

    repo.run("add", "-A")
    if not repo.is_staged_clean():
        commit_args = ["commit"]
        if args.message:
            commit_args.extend(["-m", args.message])
        else:
            commit_args.extend(["-m", "chore: update via pygit"])
        if args.allow_empty:
            commit_args.append("--allow-empty")
        repo.run(*commit_args)
    elif ahead == 0:
        printer.action("Nothing to commit and nothing ahead of upstream.")
        return 0
    repo.run("push")
    printer.action("Push complete")
    _print_ahead_files(repo, printer)
    return 0


def cmd_sync(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    repo.refresh_remotes()
    ahead, behind = repo.ahead_behind()
    exit_code = 0
    if behind > 0:
        printer.action("Sync: updating from upstream")
        if printer.apply:
            repo.run("pull", "--rebase")
        else:
            printer.action("Would run: git pull --rebase")
    if ahead > 0:
        printer.action("Sync: pushing local commits")
        if printer.apply:
            repo.run("push")
        else:
            printer.action("Would run: git push")
    if ahead == 0 and behind == 0:
        printer.action("Branch is already in sync.")
    return exit_code


def cmd_merge(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    target = args.branch
    repo.run("rev-parse", "--verify", target)
    if not printer.apply:
        printer.action(f"Would run: git merge {target}")
        return 0
    repo.run("merge", target)
    printer.action(f"Merge of {target} complete")
    return 0


def cmd_refresh_main(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    main_branch = args.main
    remote_ref = f"origin/{main_branch}"
    if not printer.apply:
        printer.action(f"Would run: git fetch origin {main_branch}")
        printer.action(f"Would run: git merge {remote_ref}")
        return 0
    repo.run("fetch", "origin", main_branch)
    repo.run("merge", remote_ref)
    printer.action(f"Merged {remote_ref} into current branch")
    return 0


def cmd_set_upstream(repo: GitRepo, printer: Printer, args: argparse.Namespace) -> int:
    repo.ensure_repo()
    remote = args.remote
    branch = args.branch
    if not printer.apply:
        printer.action(f"Would run: git branch --set-upstream-to {remote}/{branch}")
        return 0
    repo.run("branch", "--set-upstream-to", f"{remote}/{branch}")
    printer.action("Upstream configured")
    return 0


def cmd_files_to_push(repo: GitRepo, printer: Printer) -> int:
    repo.ensure_repo()
    files, reason = repo.ahead_files()
    if files is None:
        printer.warn(reason)
        return 0
    if not files:
        printer.action("No files to push")
        return 0
    for path in files:
        printer.action(path)
    return 0


HELP_EXAMPLES = """Examples:

# Dry-run push with file impact preview (default dry-run)
pygit push

# Apply push with explicit message
pygit push --apply --message "feat: add pygit CLI"

# Sync current branch safely (pull --rebase if behind; then push if ahead)
pygit sync

# Merge a branch into current (dry-run)
pygit merge feature/awesome

# Refresh current branch with latest main (apply)
pygit refresh-main --apply --main trunk

# Show which files would be pushed
pygit files-to-push

# Set upstream for current branch
pygit set-upstream origin my-branch
"""


VERBOSE_HELP = """Verbose help:
- Dry-run mode is the default; use --apply to execute commands.
- Colors: green for dry-run, blue for apply, yellow for warnings, red for errors.
- Commands shell out to git; failures bubble up as errors.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified git workflow helper")
    parser.add_argument("--apply", action="store_true", help="Execute actions instead of dry-run")
    parser.add_argument("--repo", default=".", help="Target repository (default: current directory)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--quiet", action="store_true", help="Reduce output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show repository status summary")

    pull_parser = subparsers.add_parser("pull", help="Fetch and pull updates")
    pull_parser.add_argument("--no-rebase", dest="rebase", action="store_false", help="Disable rebase when pulling")
    pull_parser.set_defaults(rebase=True)

    push_parser = subparsers.add_parser("push", help="Stage, commit, and push to upstream")
    push_parser.add_argument("-m", "--message", help="Commit message when creating a commit")
    push_parser.add_argument("--allow-empty", action="store_true", help="Allow empty commit if needed")

    subparsers.add_parser("sync", help="Pull then push to synchronize with upstream")

    merge_parser = subparsers.add_parser("merge", help="Merge a branch into current")
    merge_parser.add_argument("branch", help="Branch to merge into current")

    refresh_parser = subparsers.add_parser("refresh-main", help="Merge origin/<main> into current branch")
    refresh_parser.add_argument("--main", default="main", help="Main branch name (default: main)")

    upstream_parser = subparsers.add_parser("set-upstream", help="Set upstream for current branch")
    upstream_parser.add_argument("remote", help="Remote name")
    upstream_parser.add_argument("branch", help="Branch name")

    subparsers.add_parser("files-to-push", help="List files affected by commits ahead of upstream")
    subparsers.add_parser("help-examples", help="Show usage examples")

    return parser


def handle_args(argv: Sequence[str]) -> tuple[argparse.ArgumentParser, Optional[argparse.Namespace]]:
    if "--help-examples" in argv:
        print(HELP_EXAMPLES)
        return build_parser(), None
    if "--help-verbose" in argv:
        parser = build_parser()
        print(parser.format_help())
        print()
        print(VERBOSE_HELP)
        return parser, None
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit:
        raise
    return parser, args


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo_path = Path(args.repo).resolve()
    printer = Printer(
        apply=args.apply,
        color_enabled=not args.no_color,
        quiet=args.quiet,
        verbose=args.verbose,
    )
    repo = GitRepo(repo_path, printer)

    try:
        if args.command == "status":
            return cmd_status(repo, printer)
        if args.command == "pull":
            return cmd_pull(repo, printer, args)
        if args.command == "push":
            return cmd_push(repo, printer, args)
        if args.command == "sync":
            return cmd_sync(repo, printer, args)
        if args.command == "merge":
            return cmd_merge(repo, printer, args)
        if args.command == "refresh-main":
            return cmd_refresh_main(repo, printer, args)
        if args.command == "set-upstream":
            return cmd_set_upstream(repo, printer, args)
        if args.command == "files-to-push":
            return cmd_files_to_push(repo, printer)
        if args.command == "help-examples":
            print(HELP_EXAMPLES)
            return 0
    except GitError as exc:
        printer.error(str(exc))
        return 1
    parser.print_help()
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser, args = handle_args(argv)
    if args is None:
        return 0
    return dispatch(args, parser)


if __name__ == "__main__":
    sys.exit(main())

