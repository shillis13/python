#!/usr/bin/env python3
"""Unified git helper for dry-run/apply workflows.

This command wraps common git flows (push, pull, sync, merge, refresh)
providing a consistent dry-run preview and actionable output.  Dry-run
messages are printed in green while `--apply` switches to blue.  When pushing
it attempts to preview the files that will be affected by commits ahead of the
tracked upstream branch.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


ANSI_COLORS = {
    "green": "\033[32m",
    "blue": "\033[34m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "reset": "\033[0m",
}


class Colorizer:
    """Applies ANSI color codes when enabled."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def _wrap(self, text: str, color: str) -> str:
        if not self.enabled or not text:
            return text
        prefix = ANSI_COLORS.get(color)
        if not prefix:
            return text
        return f"{prefix}{text}{ANSI_COLORS['reset']}"

    def green(self, text: str) -> str:
        return self._wrap(text, "green")

    def blue(self, text: str) -> str:
        return self._wrap(text, "blue")

    def yellow(self, text: str) -> str:
        return self._wrap(text, "yellow")

    def red(self, text: str) -> str:
        return self._wrap(text, "red")


@dataclass
class ExecutionContext:
    repo: Path
    apply: bool
    verbose: int
    quiet: bool
    colorizer: Colorizer
    stdout: any = sys.stdout
    stderr: any = sys.stderr

    def state_color(self, text: str) -> str:
        return self.colorizer.blue(text) if self.apply else self.colorizer.green(text)

    def info(self, message: str = "") -> None:
        if self.quiet:
            return
        print(self.state_color(message), file=self.stdout)

    def plain(self, message: str = "") -> None:
        if self.quiet:
            return
        print(message, file=self.stdout)

    def warn(self, message: str) -> None:
        if self.quiet:
            return
        print(self.colorizer.yellow(message), file=self.stdout)

    def error(self, message: str) -> None:
        print(self.colorizer.red(message), file=self.stderr)


class GitError(RuntimeError):
    pass


class GitRepo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def run(self, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
        if self.verbose:
            debug = " ".join(args)
            print(f"[git] {debug}")
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if check and result.returncode != 0:
            raise GitError(result.stderr.strip() or result.stdout.strip())
        return result

    @property
    def verbose(self) -> bool:
        return bool(int(os.environ.get("PYGIT_VERBOSE", "0")))

    def ensure_repo(self) -> None:
        try:
            self.run(["rev-parse", "--show-toplevel"])
        except GitError as exc:
            raise GitError("Not a git repository") from exc

    def branch_name(self) -> Optional[str]:
        result = self.run(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        if result.returncode != 0:
            return None
        name = result.stdout.strip()
        if name == "HEAD":
            return None
        return name

    def upstream(self) -> Optional[str]:
        result = self.run(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def ahead_behind(self) -> Tuple[int, int]:
        upstream = self.upstream()
        if not upstream:
            return (0, 0)
        result = self.run(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"], check=False)
        if result.returncode != 0:
            return (0, 0)
        left, right = result.stdout.strip().split()
        return int(right), int(left)

    def porcelain(self) -> List[str]:
        result = self.run(["status", "--porcelain"], check=False)
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]

    def ahead_files(self) -> Tuple[List[str], Optional[str]]:
        upstream = self.upstream()
        if not upstream:
            return [], "No upstream configured"
        merges = self.run(["log", "--merges", f"{upstream}..HEAD"], check=False)
        if merges.returncode == 0 and merges.stdout.strip():
            return [], "Merge commits detected in pending changes"
        result = self.run(
            ["log", "--pretty=format:", "--name-only", f"{upstream}..HEAD"],
            check=False,
        )
        if result.returncode != 0:
            return [], "Unable to determine ahead commits"
        paths = sorted({line for line in result.stdout.splitlines() if line.strip()})
        return paths, None

    def has_staged_changes(self) -> bool:
        result = self.run(["diff", "--cached", "--quiet"], check=False)
        return result.returncode == 1

    def is_worktree_dirty(self) -> bool:
        return bool(self.porcelain())


def parse_porcelain(lines: Iterable[str]) -> Tuple[int, int, int]:
    staged = 0
    unstaged = 0
    untracked = 0
    for line in lines:
        if line.startswith("??"):
            untracked += 1
            continue
        if line and line[0] != " ":
            staged += 1
        if len(line) > 1 and line[1] != " ":
            unstaged += 1
    return staged, unstaged, untracked


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pygit",
        description="Unified git dry-run/apply helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", default=".", help="Repository root (default: current directory)")
    parser.add_argument("--apply", action="store_true", help="Execute commands instead of dry-run")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity")
    parser.add_argument("--quiet", action="store_true", help="Reduce non-essential output")
    parser.add_argument("--help-verbose", action="store_true", dest="help_verbose", help="Show verbose help and exit")
    parser.add_argument("--help-examples", action="store_true", dest="help_examples", help="Show usage examples and exit")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show repository status summary")

    pull = subparsers.add_parser("pull", help="Fetch and pull with rebase by default")
    pull.add_argument("--no-rebase", action="store_true", help="Use merge instead of rebase")

    push = subparsers.add_parser("push", help="Stage, commit, and push to upstream")
    push.add_argument("-m", "--message", help="Commit message to use when committing")
    push.add_argument("--allow-empty", action="store_true", help="Allow creating empty commits")
    push.add_argument("--no-stage", action="store_true", help="Skip automatic staging before commit")

    subparsers.add_parser("sync", help="Pull if behind then push if ahead")

    merge = subparsers.add_parser("merge", help="Merge a branch into the current branch")
    merge.add_argument("branch", help="Branch name to merge")

    refresh = subparsers.add_parser("refresh-main", help="Fetch and merge main branch into current")
    refresh.add_argument("--main", default="main", help="Name of the main branch (default: main)")

    set_upstream = subparsers.add_parser("set-upstream", help="Set upstream for the current branch")
    set_upstream.add_argument("remote", help="Remote name")
    set_upstream.add_argument("branch", help="Branch name")

    subparsers.add_parser("files-to-push", help="List files that would be pushed")
    subparsers.add_parser("help-examples", help="Show usage examples")

    return parser


EXAMPLES_TEXT = """Examples:
  pygit push
      Dry-run push with file impact preview.

  pygit push --apply --message "feat: add pygit CLI"
      Apply push with explicit commit message.

  pygit sync
      Safely pull (with rebase) when behind then push if ahead.

  pygit merge feature/awesome
      Preview merge of the feature/awesome branch.

  pygit refresh-main --apply --main trunk
      Update current branch with the latest trunk branch.

  pygit files-to-push
      Show unique paths touched by commits ahead of upstream.

  pygit set-upstream origin my-branch
      Set remote tracking for the current branch.
"""


VERBOSE_HELP = """pygit provides higher-level wrappers for everyday git flows.

Commands operate in dry-run mode by default which prints the actions that
would be performed using green output.  Passing --apply executes the actions
and uses blue output instead.  The command relies on the git CLI which must be
available on PATH.  In complex histories (e.g. pending merge commits) the
files-to-push preview may be skipped with a short explanation.
"""


def ensure_repo(ctx: ExecutionContext) -> GitRepo:
    repo = GitRepo(ctx.repo)
    try:
        repo.ensure_repo()
    except GitError as exc:
        ctx.error(str(exc))
        raise SystemExit(1)
    return repo


def command_status(ctx: ExecutionContext) -> int:
    repo = ensure_repo(ctx)
    branch = repo.branch_name()
    upstream = repo.upstream()
    ahead, behind = repo.ahead_behind()
    staged, unstaged, untracked = parse_porcelain(repo.porcelain())

    if branch is None:
        ctx.warn("Detached HEAD state detected")
    else:
        ctx.info(f"Branch: {branch}")
    if upstream:
        ctx.info(f"Upstream: {upstream}")
        ctx.info(f"Ahead: {ahead} | Behind: {behind}")
    else:
        ctx.warn("No upstream configured")
    ctx.info(f"Staged changes: {staged}")
    ctx.info(f"Unstaged changes: {unstaged}")
    ctx.info(f"Untracked files: {untracked}")
    return 0


def run_git_commands(ctx: ExecutionContext, repo: GitRepo, commands: List[List[str]]) -> Optional[int]:
    for args in commands:
        printable = "git " + " ".join(args)
        if ctx.apply:
            ctx.info(f"Running {printable}")
            try:
                repo.run(args)
            except GitError as exc:
                ctx.error(str(exc))
                return 1
        else:
            ctx.info(f"Would run {printable}")
    return None


def command_pull(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    repo = ensure_repo(ctx)
    commands: List[List[str]] = [["fetch"]]
    if args.no_rebase:
        commands.append(["pull"])
    else:
        commands.append(["pull", "--rebase"])
    result = run_git_commands(ctx, repo, commands)
    return result if result is not None else 0


def command_push(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    repo = ensure_repo(ctx)
    branch = repo.branch_name()
    upstream = repo.upstream()
    if branch is None:
        ctx.error("Cannot push while detached")
        return 1
    if upstream is None:
        ctx.warn("No upstream configured. Use 'pygit set-upstream <remote> <branch>'.")
        return 2

    # Keep remote tracking data fresh so ahead/behind counts are reliable.
    try:
        repo.run(["fetch", "--quiet"], check=False)
    except GitError:
        pass

    if not args.no_stage:
        if ctx.apply:
            ctx.info("Running git add -A")
            try:
                repo.run(["add", "-A"])
            except GitError as exc:
                ctx.error(str(exc))
                return 1
        else:
            ctx.info("Would run git add -A")

    if repo.has_staged_changes():
        commit_args = ["commit"]
        if args.message:
            commit_args.extend(["-m", args.message])
        else:
            commit_args.extend(["-m", "chore: update via pygit"])
        if args.allow_empty:
            commit_args.append("--allow-empty")
        if ctx.apply:
            ctx.info("Running " + "git " + " ".join(commit_args))
            try:
                repo.run(commit_args)
            except GitError as exc:
                ctx.error(str(exc))
                return 1
        else:
            ctx.info("Would run " + "git " + " ".join(commit_args))
    else:
        ctx.info("No staged changes to commit")

    ahead, behind = repo.ahead_behind()
    if behind > 0:
        ctx.warn("Push blocked because branch is behind upstream. Run 'pygit pull' first.")
        return 2
    files, reason = repo.ahead_files()
    if files:
        ctx.plain("Files to push:")
        for path in files:
            ctx.plain(f"  {path}")
    elif reason:
        ctx.warn(f"Skipped file preview: {reason}")
    else:
        ctx.info("No commits to push")

    if ahead == 0:
        return 0

    if ctx.apply:
        ctx.info("Running git push")
        try:
            repo.run(["push"])
        except GitError as exc:
            ctx.error(str(exc))
            return 1
    else:
        ctx.info("Would run git push")
    return 0


def command_sync(ctx: ExecutionContext) -> int:
    repo = ensure_repo(ctx)
    ahead, behind = repo.ahead_behind()
    if behind > 0:
        res = command_pull(ctx, argparse.Namespace(no_rebase=False))
        if res != 0:
            return res
        ahead, behind = repo.ahead_behind()
    if ahead > 0:
        push_args = argparse.Namespace(message=None, allow_empty=False, no_stage=True)
        return command_push(ctx, push_args)
    ctx.info("Branch is up to date")
    return 0


def command_merge(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    repo = ensure_repo(ctx)
    branch = args.branch
    commands = [["merge", branch]]
    result = run_git_commands(ctx, repo, commands)
    return result if result is not None else 0


def command_refresh_main(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    repo = ensure_repo(ctx)
    main_branch = args.main
    commands = [["fetch", "origin", main_branch], ["merge", f"origin/{main_branch}"]]
    result = run_git_commands(ctx, repo, commands)
    return result if result is not None else 0


def command_set_upstream(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    repo = ensure_repo(ctx)
    commands = [["branch", "--set-upstream-to", f"{args.remote}/{args.branch}"]]
    result = run_git_commands(ctx, repo, commands)
    return result if result is not None else 0


def command_files_to_push(ctx: ExecutionContext) -> int:
    repo = ensure_repo(ctx)
    files, reason = repo.ahead_files()
    if files:
        for path in files:
            ctx.plain(path)
        return 0
    if reason:
        ctx.warn(f"No file list: {reason}")
        return 2
    ctx.info("No commits ahead of upstream")
    return 0


def command_help_examples(ctx: ExecutionContext) -> int:
    ctx.plain(EXAMPLES_TEXT.rstrip())
    return 0


def dispatch(ctx: ExecutionContext, args: argparse.Namespace) -> int:
    if args.help_verbose:
        ctx.plain(VERBOSE_HELP.rstrip())
        ctx.plain("")
        ctx.plain(EXAMPLES_TEXT.rstrip())
        return 0
    if args.help_examples:
        return command_help_examples(ctx)
    if not args.command:
        ctx.error("No command provided. Use --help for usage.")
        return 1
    if args.command == "status":
        return command_status(ctx)
    if args.command == "pull":
        return command_pull(ctx, args)
    if args.command == "push":
        return command_push(ctx, args)
    if args.command == "sync":
        return command_sync(ctx)
    if args.command == "merge":
        return command_merge(ctx, args)
    if args.command == "refresh-main":
        return command_refresh_main(ctx, args)
    if args.command == "set-upstream":
        return command_set_upstream(ctx, args)
    if args.command == "files-to-push":
        return command_files_to_push(ctx)
    if args.command == "help-examples":
        return command_help_examples(ctx)
    ctx.error(f"Unknown command: {args.command}")
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    colorizer = Colorizer(enabled=not args.no_color)
    repo_path = Path(args.repo).resolve()
    os.environ["PYGIT_VERBOSE"] = "1" if args.verbose else "0"

    ctx = ExecutionContext(
        repo=repo_path,
        apply=args.apply,
        verbose=args.verbose,
        quiet=args.quiet,
        colorizer=colorizer,
    )
    try:
        return dispatch(ctx, args)
    except GitError as exc:
        ctx.error(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
