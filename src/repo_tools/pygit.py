#!/usr/bin/env python3
"""Unified git helper CLI with safe dry-run/apply behaviour.

This tool consolidates common push/pull/sync flows with colourised output
and lightweight guard rails around typical git workflows.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


RESET = "\033[0m"
COLOR_MAP = {
    "green": "\033[32m",
    "blue": "\033[34m",
    "yellow": "\033[33m",
    "red": "\033[31m",
}


def colour_text(text: str, colour: str, enabled: bool) -> str:
    if not enabled:
        return text
    code = COLOR_MAP.get(colour)
    if not code:
        return text
    return f"{code}{text}{RESET}"


class GitError(RuntimeError):
    """Raised when a git command fails."""


def _git_env() -> dict:
    env = os.environ.copy()
    env.setdefault("LC_ALL", "C")
    env.setdefault("LANG", "C")
    env.setdefault("GIT_PAGER", "cat")
    return env


def run_git(
    repo: Path,
    args: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    verbose: int = 0,
) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    kwargs = {
        "cwd": str(repo),
        "text": True,
        "env": _git_env(),
    }
    if capture_output:
        kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE})
    if verbose:
        stream = sys.stderr
        stream.write(f"[git] {' '.join(command)}\n")
    result = subprocess.run(command, **kwargs)
    if check and result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed with code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


@dataclass
class BranchInfo:
    name: str
    upstream: Optional[str]
    ahead: int
    behind: int


@dataclass
class WorkingTreeSummary:
    staged: int
    unstaged: int
    untracked: int

    @property
    def has_changes(self) -> bool:
        return any((self.staged, self.unstaged, self.untracked))


class GitRepo:
    def __init__(self, path: Path, *, verbose: int = 0) -> None:
        self.path = path
        self.verbose = verbose
        self._toplevel: Optional[Path] = None

    def ensure_repo(self) -> None:
        if self._toplevel is not None:
            return
        result = run_git(self.path, ["rev-parse", "--show-toplevel"], check=False)
        if result.returncode != 0:
            raise GitError("Not a git repository")
        self._toplevel = Path(result.stdout.strip())

    def branch_info(self) -> BranchInfo:
        self.ensure_repo()
        name = run_git(
            self.path, ["rev-parse", "--abbrev-ref", "HEAD"], verbose=self.verbose
        ).stdout.strip()
        upstream_proc = run_git(
            self.path,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            check=False,
            verbose=self.verbose,
        )
        if upstream_proc.returncode != 0:
            upstream = None
            ahead = behind = 0
        else:
            upstream = upstream_proc.stdout.strip()
            rev_list = run_git(
                self.path,
                ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"],
                verbose=self.verbose,
            )
            parts = rev_list.stdout.strip().split()
            behind = int(parts[0]) if len(parts) >= 1 else 0
            ahead = int(parts[1]) if len(parts) >= 2 else 0
        return BranchInfo(name=name, upstream=upstream, ahead=ahead, behind=behind)

    def working_tree(self) -> WorkingTreeSummary:
        self.ensure_repo()
        status = run_git(
            self.path,
            ["status", "--porcelain"],
            verbose=self.verbose,
        ).stdout.splitlines()
        staged = unstaged = untracked = 0
        for line in status:
            if not line:
                continue
            if line.startswith("??"):
                untracked += 1
                continue
            if line[0] != " ":
                staged += 1
            if len(line) > 1 and line[1] != " ":
                unstaged += 1
        return WorkingTreeSummary(staged=staged, unstaged=unstaged, untracked=untracked)

    def ahead_files(
        self, info: Optional[BranchInfo] = None
    ) -> tuple[Optional[List[str]], Optional[str]]:
        self.ensure_repo()
        if info is None:
            info = self.branch_info()
        if not info.upstream:
            return None, "No upstream configured"
        if info.ahead == 0:
            return [], None
        merges = run_git(
            self.path,
            ["rev-list", "--merges", f"{info.upstream}..HEAD"],
            verbose=self.verbose,
        ).stdout.strip()
        if merges:
            return None, "Merge commits present in ahead history"
        log_proc = run_git(
            self.path,
            ["log", f"{info.upstream}..HEAD", "--name-status", "--pretty=format:%H"],
            verbose=self.verbose,
        )
        files: set[str] = set()
        for line in log_proc.stdout.splitlines():
            if (
                not line
                or len(line) == 40
                and all(c in "0123456789abcdef" for c in line)
            ):
                continue
            status, *rest = line.split("\t")
            if not rest:
                continue
            if status and status[0] in {"R", "C"}:
                return None, "Renames or copies detected"
            files.add(rest[-1])
        return sorted(files), None

    def has_staged_changes(self) -> bool:
        proc = run_git(
            self.path,
            ["diff", "--cached", "--quiet"],
            check=False,
            verbose=self.verbose,
        )
        return proc.returncode == 1

    def add_all(self) -> None:
        run_git(self.path, ["add", "-A"], verbose=self.verbose)

    def commit(self, message: str, *, allow_empty: bool = False) -> None:
        args = ["commit", "-m", message]
        if allow_empty:
            args.insert(1, "--allow-empty")
        run_git(self.path, args, verbose=self.verbose)

    def push(self) -> None:
        run_git(self.path, ["push"], verbose=self.verbose)

    def pull(self, *, rebase: bool) -> None:
        run_git(self.path, ["fetch", "--prune"], verbose=self.verbose)
        pull_args = ["pull"]
        if rebase:
            pull_args.append("--rebase")
        run_git(self.path, pull_args, verbose=self.verbose)

    def merge(self, branch: str, *, ff_only: bool = False) -> None:
        args = ["merge"]
        if ff_only:
            args.append("--ff-only")
        args.append(branch)
        run_git(self.path, args, verbose=self.verbose)


class Printer:
    def __init__(self, *, apply_mode: bool, colour: bool, quiet: bool) -> None:
        self.apply_mode = apply_mode
        self.colour = colour
        self.quiet = quiet

    def _channel(self) -> str:
        return "blue" if self.apply_mode else "green"

    def info(self, text: str) -> None:
        if self.quiet:
            return
        print(colour_text(text, self._channel(), self.colour))

    def warn(self, text: str) -> None:
        print(colour_text(text, "yellow", self.colour), file=sys.stderr)

    def error(self, text: str) -> None:
        print(colour_text(text, "red", self.colour), file=sys.stderr)


def command_status(repo: GitRepo, printer: Printer) -> int:
    info = repo.branch_info()
    wt = repo.working_tree()
    printer.info(
        f"Branch: {info.name} | Upstream: {info.upstream or 'none'} | "
        f"Ahead: {info.ahead} | Behind: {info.behind}"
    )
    if wt.has_changes:
        printer.info(
            f"Working tree — staged: {wt.staged}, unstaged: {wt.unstaged}, "
            f"untracked: {wt.untracked}"
        )
    else:
        printer.info("Working tree clean")
    if not info.upstream:
        printer.warn(
            "No upstream configured. Use 'pygit set-upstream <remote> <branch>'."
        )
    return 0


def print_files_preview(
    files: Optional[List[str]], reason: Optional[str], printer: Printer
) -> None:
    if files is None:
        printer.warn(f"File preview skipped: {reason}")
        return
    if not files:
        printer.info("No pending commits to preview.")
        return
    printer.info("Files that would be pushed:")
    for path in files:
        printer.info(f"  {path}")


def command_pull(args: argparse.Namespace, repo: GitRepo, printer: Printer) -> int:
    summary = "Running" if printer.apply_mode else "Would run"
    printer.info(f"{summary} git fetch --prune")
    pull_desc = "git pull --rebase" if args.rebase else "git pull"
    printer.info(f"{summary} {pull_desc}")
    if not printer.apply_mode:
        return 0
    repo.pull(rebase=args.rebase)
    return 0


def command_push(args: argparse.Namespace, repo: GitRepo, printer: Printer) -> int:
    info = repo.branch_info()
    wt = repo.working_tree()
    if not info.upstream:
        printer.error("Push aborted: no upstream configured. Use 'pygit set-upstream'.")
        return 2
    if info.behind:
        printer.warn(
            f"Push blocked: branch is behind upstream by {info.behind} commit(s)."
        )
        printer.warn("Run 'pygit pull --rebase' or 'pygit sync' first.")
        return 2
    files, reason = repo.ahead_files(info)
    if wt.has_changes:
        printer.info(
            f"Working tree — staged: {wt.staged}, unstaged: {wt.unstaged}, "
            f"untracked: {wt.untracked}"
        )
    else:
        printer.info("Working tree clean")
    print_files_preview(files, reason, printer)
    if not printer.apply_mode:
        printer.info("Would stage all changes (git add -A)")
        printer.info(
            "Would commit staged changes"
            if args.message
            else "Would create commit if staged changes exist"
        )
        printer.info("Would push to upstream")
        return 0

    printer.info("Running git add -A")
    repo.add_all()
    default_message = "chore: update via pygit"
    commit_message = args.message or default_message
    if repo.has_staged_changes() or args.allow_empty:
        commit_line = f"Running git commit -m '{commit_message}'"
        if args.allow_empty:
            commit_line += " (allow-empty)"
        printer.info(commit_line)
        repo.commit(commit_message, allow_empty=args.allow_empty)
    post_info = repo.branch_info()
    if post_info.ahead == 0:
        printer.warn("Nothing to push; branch not ahead of upstream.")
        return 0
    printer.info("Running git push")
    repo.push()
    return 0


def command_sync(args: argparse.Namespace, repo: GitRepo, printer: Printer) -> int:
    info = repo.branch_info()
    exit_code = 0
    if info.behind:
        printer.info(
            f"Branch behind upstream by {info.behind} commit(s); performing pull --rebase."
        )
        if printer.apply_mode:
            printer.info("Running git fetch --prune")
            printer.info("Running git pull --rebase")
            repo.pull(rebase=True)
        else:
            printer.info("Would run: git fetch --prune")
            printer.info("Would run: git pull --rebase")
        info = repo.branch_info()
    if info.ahead:
        printer.info(f"Branch ahead by {info.ahead} commit(s); pushing to upstream.")
        if not printer.apply_mode:
            printer.info("Would run: git push")
        else:
            printer.info("Running git push")
            repo.push()
    else:
        printer.info("Nothing to push.")
    return exit_code


def command_merge(args: argparse.Namespace, repo: GitRepo, printer: Printer) -> int:
    target = args.branch
    exists = run_git(repo.path, ["rev-parse", "--verify", target], check=False)
    if exists.returncode != 0:
        printer.error(f"Branch '{target}' not found.")
        return 1
    ff_possible = (
        run_git(
            repo.path,
            ["merge-base", "--is-ancestor", "HEAD", target],
            check=False,
        ).returncode
        == 0
    )
    if ff_possible:
        printer.info(f"Merging {target} would fast-forward current branch.")
    else:
        printer.info(f"Merging {target} requires a merge commit.")
    if not printer.apply_mode:
        printer.info(f"Would run: git merge {target}")
        return 0
    repo.merge(target, ff_only=False)
    return 0


def command_refresh_main(
    args: argparse.Namespace, repo: GitRepo, printer: Printer
) -> int:
    main_branch = args.main
    remote_ref = f"origin/{main_branch}"
    if not printer.apply_mode:
        printer.info(f"Would run: git fetch origin {main_branch}")
        printer.info(f"Would merge {remote_ref} into current branch")
        return 0
    printer.info(f"Running git fetch origin {main_branch}")
    run_git(repo.path, ["fetch", "origin", main_branch])
    printer.info(f"Running git merge {remote_ref}")
    repo.merge(remote_ref, ff_only=False)
    return 0


def command_set_upstream(
    args: argparse.Namespace, repo: GitRepo, printer: Printer
) -> int:
    remote = args.remote
    branch = args.branch
    if not printer.apply_mode:
        printer.info(f"Would run: git branch --set-upstream-to={remote}/{branch}")
        return 0
    printer.info(f"Running git branch --set-upstream-to={remote}/{branch}")
    run_git(repo.path, ["branch", f"--set-upstream-to={remote}/{branch}"])
    return 0


def command_files_to_push(
    args: argparse.Namespace, repo: GitRepo, printer: Printer
) -> int:
    info = repo.branch_info()
    files, reason = repo.ahead_files(info)
    if files is None:
        printer.warn(f"File listing unavailable: {reason}")
        return 0
    if not files:
        printer.info("No commits ahead of upstream.")
        return 0
    for path in files:
        printer.info(path)
    return 0


HELP_EXAMPLES = """
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
""".strip()


def print_verbose_help() -> None:
    message = """
pygit — Unified git helper

The tool operates in dry-run mode by default (green output). Use --apply to
execute the described operations (blue output). When pushing, pygit attempts to
enumerate files touched by commits ahead of the upstream branch. The listing is
skipped if the history contains merges or renames.

Exit codes:
  0 - success
  1 - unexpected error
  2 - precondition failure (e.g. push while behind)

Commands include: status, pull, push, sync, merge, refresh-main,
set-upstream, files-to-push.
""".strip()
    print(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified git helper with dry-run safety"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Execute commands (default dry-run)"
    )
    parser.add_argument(
        "--repo", default=".", help="Path to repository (default: current directory)"
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colour output")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress non-essential output"
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show repository status")

    pull_parser = subparsers.add_parser("pull", help="Fetch and pull (default rebase)")
    pull_parser.add_argument("--rebase", action="store_true", default=True)
    pull_parser.add_argument("--no-rebase", dest="rebase", action="store_false")

    push_parser = subparsers.add_parser("push", help="Stage, commit and push changes")
    push_parser.add_argument("--message", help="Commit message to use when committing")
    push_parser.add_argument(
        "--allow-empty", action="store_true", help="Allow empty commit"
    )

    subparsers.add_parser("sync", help="Pull (rebase) if behind then push if ahead")

    merge_parser = subparsers.add_parser("merge", help="Merge a branch into current")
    merge_parser.add_argument("branch")

    refresh_parser = subparsers.add_parser(
        "refresh-main", help="Fetch and merge the latest main branch"
    )
    refresh_parser.add_argument(
        "--main", default="main", help="Name of the main branch (default: main)"
    )

    upstream_parser = subparsers.add_parser(
        "set-upstream", help="Set upstream for current branch"
    )
    upstream_parser.add_argument("remote")
    upstream_parser.add_argument("branch")

    subparsers.add_parser(
        "files-to-push", help="List files contained in commits ahead of upstream"
    )

    subparsers.add_parser("help-examples", help="Show common usage examples")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv or sys.argv[1:])
    if "--help-examples" in argv:
        print(HELP_EXAMPLES)
        return 0
    if "--help-verbose" in argv:
        print_verbose_help()
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "help-examples":
        print(HELP_EXAMPLES)
        return 0

    repo_path = Path(args.repo).resolve()
    repo = GitRepo(repo_path, verbose=args.verbose)
    printer = Printer(
        apply_mode=args.apply,
        colour=not args.no_color,
        quiet=args.quiet,
    )
    try:
        if args.command == "status":
            return command_status(repo, printer)
        if args.command == "pull":
            return command_pull(args, repo, printer)
        if args.command == "push":
            return command_push(args, repo, printer)
        if args.command == "sync":
            return command_sync(args, repo, printer)
        if args.command == "merge":
            return command_merge(args, repo, printer)
        if args.command == "refresh-main":
            return command_refresh_main(args, repo, printer)
        if args.command == "set-upstream":
            return command_set_upstream(args, repo, printer)
        if args.command == "files-to-push":
            return command_files_to_push(args, repo, printer)
        if args.command == "help-examples":
            print(HELP_EXAMPLES)
            return 0
        parser.error(f"Unknown command {args.command}")
    except GitError as exc:
        printer.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
