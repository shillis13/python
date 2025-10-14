#!/usr/bin/env python3
"""Unified git helper CLI with dry-run/apply semantics.

This module provides a small wrapper around the git command-line to unify
push/pull workflows with a single entry point.  The default mode is a safe
"dry run" which prints the actions that would be taken using green output.  If
``--apply`` is supplied, actions are executed and output uses blue.  Additional
subcommands cover sync, merge, refresh-main, and utilities for inspecting which
files would be pushed.

The implementation shells out to ``git`` and keeps the interface minimal so it
can run in environments where GitPython is unavailable.  Tests interact with it
via subprocesses using temporary git repositories.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

DRY_RUN_COLOR = "green"
APPLY_COLOR = "blue"
WARN_COLOR = "yellow"
ERROR_COLOR = "red"


class CLIError(RuntimeError):
    """Raised when a command should exit with a specific status code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class Colorizer:
    """Simple ANSI color helper."""

    enabled: bool = True

    CODES = {
        "reset": "\033[0m",
        "green": "\033[32m",
        "blue": "\033[34m",
        "yellow": "\033[33m",
        "red": "\033[31m",
    }

    def apply(self, color: str, text: str) -> str:
        if not self.enabled or color not in self.CODES:
            return text
        return f"{self.CODES[color]}{text}{self.CODES['reset']}"


@dataclass
class OutputManager:
    """Manage formatted output with respect to dry-run/apply semantics."""

    apply_mode: bool
    colorizer: Colorizer
    quiet: bool = False

    def info(self, text: str) -> None:
        if self.quiet:
            return
        color = APPLY_COLOR if self.apply_mode else DRY_RUN_COLOR
        print(self.colorizer.apply(color, text))

    def warning(self, text: str) -> None:
        if self.quiet:
            return
        print(self.colorizer.apply(WARN_COLOR, text))

    def error(self, text: str) -> None:
        print(self.colorizer.apply(ERROR_COLOR, text), file=sys.stderr)


class GitRunner:
    """Thin wrapper around ``git`` shell commands."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        if not self.repo.exists():
            raise CLIError(f"Repository path does not exist: {self.repo}")
        if not self._is_git_repo():
            raise CLIError("Not a git repository (missing .git directory)")

    def _is_git_repo(self) -> bool:
        try:
            self.run(["git", "rev-parse", "--is-inside-work-tree"], check=True)
        except CLIError:
            return False
        return True

    def run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            args,
            cwd=str(self.repo),
            check=False,
            capture_output=capture_output,
            text=text,
        )
        if check and result.returncode != 0:
            raise CLIError(
                f"git command failed: {' '.join(shlex.quote(a) for a in args)}\n"
                f"{result.stderr.strip() or result.stdout.strip()}",
                exit_code=result.returncode or 1,
            )
        return result

    def branch_name(self) -> str:
        result = self.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def upstream(self) -> str | None:
        result = self.run(
            ["git", "rev-parse", "--symbolic-full-name", "@{u}"],
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def ahead_behind(self) -> tuple[int, int]:
        upstream = self.upstream()
        if not upstream:
            return (0, 0)
        result = self.run(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
        )
        ahead_str, behind_str = result.stdout.strip().split()
        return (int(ahead_str), int(behind_str))

    def working_tree_state(self) -> dict[str, List[str]]:
        result = self.run(["git", "status", "--porcelain"])
        staged: List[str] = []
        unstaged: List[str] = []
        untracked: List[str] = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            status = line[:2]
            path = line[3:]
            if status[0] != " " and status[0] != "?":
                staged.append(path)
            if status[1] != " " and status[1] != "?":
                unstaged.append(path)
            if status.startswith("??"):
                untracked.append(path)
        return {"staged": staged, "unstaged": unstaged, "untracked": untracked}

    def ahead_files(self) -> tuple[List[str], str | None]:
        upstream = self.upstream()
        if not upstream:
            return ([], "No upstream configured")
        merges = self.run(
            ["git", "rev-list", "--merges", f"{upstream}..HEAD"],
        ).stdout.strip()
        if merges:
            return ([], "Merge commits ahead of upstream; skipping list")
        log = self.run(
            [
                "git",
                "log",
                "--name-status",
                "--pretty=format:%H",
                f"{upstream}..HEAD",
            ]
        ).stdout
        files = set()
        for line in log.splitlines():
            if not line or "\t" not in line:
                continue
            status, path = line.split("\t", 1)
            if status.startswith("R"):
                return ([], "Renames detected; skipping file preview")
            files.add(path)
        return (sorted(files), None)

    def stage_all(self) -> None:
        self.run(["git", "add", "-A"])

    def commit(self, message: str, allow_empty: bool = False) -> bool:
        args = ["git", "commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        result = self.run(args, check=False)
        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                return False
            raise CLIError(result.stderr.strip() or result.stdout.strip(), result.returncode)
        return True

    def push(self) -> None:
        upstream = self.upstream()
        args = ["git", "push"]
        if upstream is None:
            raise CLIError("No upstream configured. Use set-upstream first.", exit_code=2)
        self.run(args)

    def fetch(self, remote: str | None = None) -> None:
        args = ["git", "fetch"]
        if remote:
            args.append(remote)
        self.run(args)

    def pull(self, *, rebase: bool = True) -> None:
        args = ["git", "pull"]
        if rebase:
            args.append("--rebase")
        self.run(args)

    def merge(self, branch: str) -> None:
        self.run(["git", "merge", branch])

    def merge_base(self, branch: str, other: str) -> str:
        result = self.run(["git", "merge-base", branch, other])
        return result.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified git helper CLI")
    parser.add_argument("--apply", action="store_true", help="Execute actions instead of dry-run")
    parser.add_argument("--repo", default=".", help="Path to the git repository")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational output")
    parser.add_argument("--help-verbose", action="store_true", help="Show verbose help and exit")
    parser.add_argument(
        "--help-examples", action="store_true", help="Show usage examples and exit"
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show repository status summary")

    pull_parser = subparsers.add_parser("pull", help="Fetch and pull (rebase by default)")
    pull_parser.add_argument("--no-rebase", action="store_true", help="Do not use --rebase")

    push_parser = subparsers.add_parser("push", help="Stage, commit, and push changes")
    push_parser.add_argument("--message", "-m", help="Commit message to use")
    push_parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow creating empty commits",
    )
    push_parser.add_argument(
        "--no-stage",
        action="store_true",
        help="Do not run git add -A before committing",
    )

    subparsers.add_parser("sync", help="Pull if behind then push if ahead")

    merge_parser = subparsers.add_parser("merge", help="Merge another branch into the current")
    merge_parser.add_argument("branch", help="Branch to merge into the current branch")

    refresh_parser = subparsers.add_parser(
        "refresh-main", help="Fetch and merge the main branch into the current"
    )
    refresh_parser.add_argument("--main", default="main", help="Name of the main branch")

    set_up_parser = subparsers.add_parser(
        "set-upstream", help="Set upstream for current branch"
    )
    set_up_parser.add_argument("remote", help="Remote name")
    set_up_parser.add_argument("branch", help="Remote branch")

    subparsers.add_parser("files-to-push", help="List files that would be pushed")
    subparsers.add_parser("help-examples", help="Show usage examples")

    return parser


EXAMPLES = """Examples:
  pygit push
  pygit push --apply --message "feat: add pygit CLI"
  pygit sync
  pygit merge feature/awesome
  pygit refresh-main --apply --main trunk
  pygit files-to-push
  pygit set-upstream origin my-branch
"""

VERBOSE_HELP = """pygit extends git with a consistent dry-run workflow.

Status information comes from `git status --porcelain` and `git rev-list` to
calculate ahead/behind counts.  Dry-run output uses green text, while applying
changes uses blue text.  Warnings and errors use yellow and red respectively.

Most subcommands simply wrap the equivalent git commands; they are always
printed before being executed in apply mode when verbosity is enabled.
"""


def ensure_command(args: argparse.Namespace) -> str:
    if args.command:
        return args.command
    return "status"


def format_cmd(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def cmd_status(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    branch = runner.branch_name()
    upstream = runner.upstream() or "<none>"
    ahead, behind = runner.ahead_behind()
    state = runner.working_tree_state()
    summary = [
        f"On branch {branch}",
        f"Upstream: {upstream}",
        f"Ahead by {ahead} commit(s)",
        f"Behind by {behind} commit(s)",
        f"Staged changes: {len(state['staged'])}",
        f"Unstaged changes: {len(state['unstaged'])}",
        f"Untracked files: {len(state['untracked'])}",
    ]
    out.info("; ".join(summary))
    if upstream == "<none>":
        out.warning("No upstream configured. Use set-upstream to configure one.")
        return 2
    return 0


def cmd_pull(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    rebase = not args.no_rebase
    if not out.apply_mode:
        out.info(
            "Would run: "
            + " -> ".join(
                [
                    format_cmd(["git", "fetch"]),
                    format_cmd(["git", "pull"] + (["--rebase"] if rebase else [])),
                ]
            )
        )
        return 0
    runner.fetch()
    runner.pull(rebase=rebase)
    out.info("Fetch and pull completed")
    return 0


def guard_push_state(runner: GitRunner, out: OutputManager) -> tuple[int, int]:
    ahead, behind = runner.ahead_behind()
    if behind:
        raise CLIError(
            "Cannot push: branch is behind upstream. Run pygit pull or sync first.",
            exit_code=2,
        )
    return ahead, behind


def cmd_push(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    ahead_before, _ = guard_push_state(runner, out)
    files, skip_reason = runner.ahead_files()
    if skip_reason:
        out.warning(skip_reason)
    elif files:
        out.info("Files to push:\n" + "\n".join(f"  {path}" for path in files))
    else:
        out.info("No commits ahead of upstream")
    commit_message = args.message or "chore: sync via pygit"

    if not out.apply_mode:
        planned: List[str] = []
        if not args.no_stage:
            planned.append(format_cmd(["git", "add", "-A"]))
        planned.append(format_cmd(["git", "commit", "-m", commit_message]))
        planned.append(format_cmd(["git", "push"]))
        out.info("Would run: \n" + "\n".join(planned))
        return 0

    if not args.no_stage:
        runner.stage_all()
    committed = runner.commit(commit_message, allow_empty=args.allow_empty)
    if committed:
        out.info("Commit created")
    else:
        out.warning("Nothing to commit")
    guard_push_state(runner, out)
    runner.push()
    out.info("Push completed")
    return 0


def cmd_sync(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    ahead, behind = runner.ahead_behind()
    actions: List[str] = []
    if behind:
        actions.append("pull --rebase")
    if ahead:
        actions.append("push")
    if not actions:
        out.info("Branch is in sync with upstream")
        return 0
    if not out.apply_mode:
        out.info("Would run: " + " then ".join(actions))
        return 0
    if behind:
        runner.fetch()
        runner.pull(rebase=True)
        out.info("Rebased onto upstream")
    ahead_after, _ = runner.ahead_behind()
    if ahead_after:
        runner.push()
        out.info("Push completed")
    else:
        out.info("No commits to push after pulling")
    return 0


def cmd_merge(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    branch = args.branch
    if not out.apply_mode:
        out.info(f"Would run: {format_cmd(['git', 'merge', branch])}")
        return 0
    runner.merge(branch)
    out.info(f"Merged {branch} into current branch")
    return 0


def cmd_refresh_main(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    main_branch = args.main
    fetch_cmd = ["git", "fetch", "origin", main_branch]
    merge_cmd = ["git", "merge", f"origin/{main_branch}"]
    if not out.apply_mode:
        out.info(
            "Would run: "
            + " -> ".join([format_cmd(fetch_cmd), format_cmd(merge_cmd)])
        )
        return 0
    runner.fetch("origin")
    runner.run(merge_cmd)
    out.info(f"Merged origin/{main_branch} into current branch")
    return 0


def cmd_set_upstream(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    cmd = ["git", "branch", "--set-upstream-to", f"{args.remote}/{args.branch}"]
    if not out.apply_mode:
        out.info(f"Would run: {format_cmd(cmd)}")
        return 0
    runner.run(cmd)
    out.info(f"Upstream set to {args.remote}/{args.branch}")
    return 0


def cmd_files_to_push(runner: GitRunner, out: OutputManager, args: argparse.Namespace) -> int:
    files, skip_reason = runner.ahead_files()
    if skip_reason:
        out.warning(skip_reason)
        return 2
    if not files:
        out.info("No files to push")
        return 0
    out.info("\n".join(files))
    return 0


def cmd_help_examples(out: OutputManager) -> int:
    print(EXAMPLES)
    return 0


COMMANDS = {
    "status": cmd_status,
    "pull": cmd_pull,
    "push": cmd_push,
    "sync": cmd_sync,
    "merge": cmd_merge,
    "refresh-main": cmd_refresh_main,
    "set-upstream": cmd_set_upstream,
    "files-to-push": cmd_files_to_push,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.help_verbose:
        print(VERBOSE_HELP)
        return 0
    if args.help_examples and args.command is None:
        print(EXAMPLES)
        return 0

    command_name = ensure_command(args)
    if command_name == "help-examples":
        print(EXAMPLES)
        return 0

    colorizer = Colorizer(enabled=not args.no_color)
    out = OutputManager(apply_mode=args.apply, colorizer=colorizer, quiet=args.quiet)

    try:
        runner = GitRunner(Path(args.repo).resolve())
    except CLIError as exc:
        out.error(str(exc))
        return exc.exit_code

    command = COMMANDS.get(command_name)
    if not command:
        out.error(f"Unknown command: {command_name}")
        return 1

    try:
        return command(runner, out, args)
    except CLIError as exc:
        out.error(str(exc))
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
