from pathlib import Path
from typing import Callable

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from dev_utils.lib_logging import log_debug, log_error


def build_ignore_filter(base_dir: Path, use_gitignore: bool) -> Callable[[Path], bool]:
    """Return a predicate that checks if a path should be included."""
    spec = None
    if use_gitignore:
        gitignore = base_dir / ".gitignore"
        if gitignore.exists():
            patterns = gitignore.read_text().splitlines()
            spec = PathSpec.from_lines(GitWildMatchPattern, patterns)
            log_debug(f"Loaded .gitignore from {gitignore}")
        else:
            log_error(f".gitignore not found in {base_dir}")

    def include(path: Path) -> bool:
        if spec is None:
            return True
        relative = path.relative_to(base_dir)
        return not spec.match_file(str(relative))

    return include
