#!/usr/bin/env python3
"""
Directory Structure Discovery Tool

Crawls directory trees and generates annotated structure views by extracting
description metadata from files and READMEs.

Usage:
    dir_struct_discovery.py [path] [options]
    
Examples:
    dir_struct_discovery.py ~/Documents/AI/Claude/claude_workspace
    dir_struct_discovery.py . --depth 2 --format json
    dir_struct_discovery.py ~/projects --include-hidden --format markdown
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
import yaml


DEFAULT_EXCLUDES = [
    "node_modules/",
    "__pycache__/",
    ".git/",
    "*.pyc",
]


@dataclass
class FileInfo:
    """Metadata extracted from a file."""
    name: str
    path: str
    type: str  # 'file', 'dir', 'symlink'
    description: Optional[str] = None
    size: Optional[int] = None
    has_metadata: bool = False


@dataclass
class DirectoryStats:
    """Statistics about directory structure."""
    total_files: int = 0
    total_dirs: int = 0
    documented_files: int = 0
    documented_dirs: int = 0
    
    @property
    def doc_percentage(self) -> float:
        """Percentage of documented items."""
        total = self.total_files + self.total_dirs
        documented = self.documented_files + self.documented_dirs
        return (documented / total * 100) if total > 0 else 0.0


@dataclass
class GitAllowlist:
    """Files and directories permitted by git (respecting .gitignore)."""
    allowed_files: Set[str]
    allowed_dirs: Set[str]
    repo_root: Path
    rel_root: Path


def _discover_git_root(root_path: Path) -> Optional[Path]:
    """Return git repo root containing root_path, if any."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return Path(result.stdout.strip())
    except FileNotFoundError:
        return None


def _normalize_git_path(path: Path) -> str:
    """Return POSIX-style relative path string for matching."""
    if path == Path("."):
        return "."
    return path.as_posix()


def build_git_allowlist(root_path: Path, include_untracked: bool) -> Optional[GitAllowlist]:
    """
    Build allowlist of files/dirs using git ls-files to honor .gitignore.

    When include_untracked=True, include untracked-but-not-ignored files.
    """
    repo_root = _discover_git_root(root_path)
    if not repo_root:
        return None

    try:
        rel_root = root_path.relative_to(repo_root)
    except ValueError:
        # root_path not inside repo_root
        return None

    command = ["git", "-C", str(repo_root), "ls-files", "-z"]
    if include_untracked:
        command = [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]

    if rel_root != Path("."):
        command.extend(["--", rel_root.as_posix()])

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None

    entries = [p for p in result.stdout.split("\0") if p]
    allowed_files: Set[str] = set()
    allowed_dirs: Set[str] = {"."}

    prefix = "" if rel_root == Path(".") else rel_root.as_posix().rstrip("/") + "/"
    for entry in entries:
        relative_entry = entry
        if prefix and entry.startswith(prefix):
            relative_entry = entry[len(prefix) :]
        path_obj = Path(relative_entry)
        rel_str = _normalize_git_path(path_obj)
        allowed_files.add(rel_str)
        for parent in path_obj.parents:
            rel_parent = _normalize_git_path(parent)
            allowed_dirs.add(rel_parent)

    return GitAllowlist(
        allowed_files=allowed_files,
        allowed_dirs=allowed_dirs,
        repo_root=repo_root,
        rel_root=rel_root,
    )


def load_patterns_from_file(file_path: Path) -> List[str]:
    """Read exclude patterns from a file, ignoring blank/comment lines."""
    patterns: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                patterns.append(stripped)
    except OSError as exc:
        print(f"Warning: unable to read exclude file {file_path}: {exc}", file=sys.stderr)
    return patterns


def load_gitignore_patterns(root_path: Path, max_depth: int) -> List[str]:
    """
    Gather .gitignore rules as exclusion patterns when git is unavailable.

    This is a best-effort fallback and ignores negation rules.
    """
    patterns: List[str] = []
    for current_dir, dirnames, filenames in os.walk(root_path):
        relative_dir = Path(current_dir).relative_to(root_path)
        if len(relative_dir.parts) > max_depth:
            dirnames[:] = []
            continue

        if ".gitignore" not in filenames:
            continue

        gitignore_path = Path(current_dir) / ".gitignore"
        prefix = "" if relative_dir == Path(".") else relative_dir.as_posix().rstrip("/") + "/"
        for pattern in load_patterns_from_file(gitignore_path):
            # Negation is not supported in this fallback path.
            if pattern.startswith("!"):
                continue
            cleaned = pattern.lstrip("/")
            adjusted = f"{prefix}{cleaned}" if prefix else cleaned
            patterns.append(adjusted)

    return patterns


@dataclass
class ExcludePattern:
    """Compiled exclude pattern (glob or regex)."""

    raw: str
    is_regex: bool
    pattern: str
    compiled: Optional[re.Pattern]
    dir_only: bool

    def matches(self, path_str: str, name: str, is_dir: bool) -> bool:
        if self.dir_only and not is_dir:
            return False

        target = path_str
        if self.is_regex:
            assert self.compiled is not None
            return bool(self.compiled.search(target))

        return fnmatch.fnmatch(target, self.pattern) or fnmatch.fnmatch(name, self.pattern)


class PathFilter:
    """Centralized path filtering (hidden files, excludes, gitignore)."""

    def __init__(
        self,
        root_path: Path,
        include_hidden: bool,
        exclude_patterns: List[str],
        git_allowlist: Optional[GitAllowlist] = None,
    ):
        self.root_path = root_path
        self.include_hidden = include_hidden
        self.git_allowlist = git_allowlist
        self.patterns = self._compile_patterns(DEFAULT_EXCLUDES + exclude_patterns)

    def _compile_patterns(self, patterns: List[str]) -> List[ExcludePattern]:
        compiled: List[ExcludePattern] = []
        for raw in patterns:
            if not raw:
                continue
            is_regex = raw.startswith("re:") or raw.startswith("regex:")
            pattern_body = raw.split(":", 1)[1] if is_regex else raw
            dir_only = pattern_body.endswith("/")
            normalized = pattern_body.rstrip("/")
            if normalized.startswith("/"):
                normalized = normalized.lstrip("/")

            compiled_regex: Optional[re.Pattern] = None
            if is_regex:
                try:
                    compiled_regex = re.compile(normalized)
                except re.error as exc:
                    print(f"Warning: invalid regex exclude pattern '{raw}': {exc}", file=sys.stderr)
                    continue

            compiled.append(
                ExcludePattern(
                    raw=raw,
                    is_regex=is_regex,
                    pattern=normalized,
                    compiled=compiled_regex,
                    dir_only=dir_only,
                )
            )
        return compiled

    def _relative_to_root(self, path: Path) -> str:
        try:
            rel_path = path.relative_to(self.root_path)
            return "." if rel_path == Path(".") else rel_path.as_posix()
        except ValueError:
            return path.as_posix()

    def should_skip(self, path: Path, is_dir: bool) -> bool:
        name = path.name
        if not self.include_hidden and name.startswith("."):
            return True

        rel_path_str = self._relative_to_root(path)

        if self.git_allowlist:
            if rel_path_str != ".":
                if is_dir and rel_path_str not in self.git_allowlist.allowed_dirs:
                    return True
                if not is_dir and rel_path_str not in self.git_allowlist.allowed_files:
                    return True

        for pattern in self.patterns:
            if pattern.matches(rel_path_str, name, is_dir):
                return True

        return False


class MetadataExtractor:
    """Extract description metadata from various file formats."""
    
    @staticmethod
    def extract_yaml_description(filepath: Path) -> Optional[str]:
        """Extract description from YAML file frontmatter."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Try to parse frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        if isinstance(frontmatter, dict):
                            return frontmatter.get('description')
        except Exception:
            pass
        return None
    
    @staticmethod
    def extract_json_description(filepath: Path) -> Optional[str]:
        """Extract description from JSON _meta field."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if '_meta' in data and isinstance(data['_meta'], dict):
                    return data['_meta'].get('description')
        except Exception:
            pass
        return None
    
    @staticmethod
    def extract_markdown_description(filepath: Path) -> Optional[str]:
        """Extract description from Markdown frontmatter or first paragraph."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Try frontmatter first
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        if isinstance(frontmatter, dict) and 'description' in frontmatter:
                            return frontmatter['description']
                        # Use body content after frontmatter
                        content = parts[2]
                
                # Extract first paragraph (up to first period or 200 chars)
                # Remove markdown headers
                content = re.sub(r'^#+\s+', '', content.strip(), flags=re.MULTILINE)
                # Get first non-empty line
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Get up to first period or 200 chars
                        match = re.match(r'^(.{1,200}?)[.!?]', line)
                        if match:
                            return match.group(1).strip()
                        return line[:200]
        except Exception:
            pass
        return None
    
    @classmethod
    def extract_description(cls, filepath: Path) -> Optional[str]:
        """Extract description based on file extension."""
        suffix = filepath.suffix.lower()
        
        if suffix in ['.yml', '.yaml']:
            return cls.extract_yaml_description(filepath)
        elif suffix == '.json':
            return cls.extract_json_description(filepath)
        elif suffix in ['.md', '.markdown']:
            return cls.extract_markdown_description(filepath)
        
        return None


class DirectoryDiscovery:
    """Main directory structure discovery engine."""
    
    def __init__(
        self,
        root_path: Path,
        max_depth: int = 3,
        include_hidden: bool = False,
        path_filter: Optional[PathFilter] = None,
    ):
        self.max_depth = max_depth
        self.include_hidden = include_hidden
        self.stats = DirectoryStats()
        self.extractor = MetadataExtractor()
        self.root_path = root_path
        self.path_filter = path_filter or PathFilter(root_path, include_hidden, [])
    
    def should_process(self, path: Path, is_dir: bool) -> bool:
        """Determine if path should be processed."""
        return not self.path_filter.should_skip(path, is_dir)
    
    def scan_directory(self, root_path: Path, current_depth: int = 0) -> List[FileInfo]:
        """Recursively scan directory and extract metadata."""
        items = []
        
        if current_depth > self.max_depth:
            return items
        
        try:
            entries = sorted(root_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            
            for entry in entries:
                is_dir = entry.is_dir()
                if not self.should_process(entry, is_dir):
                    continue
                
                # Determine type
                if entry.is_symlink():
                    file_type = 'symlink'
                    target = os.readlink(str(entry))
                    description = f"→ {target}"
                    has_metadata = False
                elif is_dir:
                    file_type = 'dir'
                    self.stats.total_dirs += 1
                    # Check for README
                    readme = entry / 'README.md'
                    description = None
                    if readme.exists():
                        description = self.extractor.extract_description(readme)
                    has_metadata = description is not None
                    if has_metadata:
                        self.stats.documented_dirs += 1
                else:
                    file_type = 'file'
                    self.stats.total_files += 1
                    description = self.extractor.extract_description(entry)
                    has_metadata = description is not None
                    if has_metadata:
                        self.stats.documented_files += 1
                
                info = FileInfo(
                    name=entry.name,
                    path=str(entry),
                    type=file_type,
                    description=description,
                    size=entry.stat().st_size if entry.is_file() else None,
                    has_metadata=has_metadata
                )
                items.append(info)
                
                # Recurse into directories
                if file_type == 'dir':
                    children = self.scan_directory(entry, current_depth + 1)
                    # Store children in a way that formatters can access
                    # For now, we'll handle this in the formatter
        
        except PermissionError:
            pass  # Skip directories we can't access
        
        return items


class OutputFormatter:
    """Format directory structure output."""
    
    @staticmethod
    def format_tree(root_path: Path, items: List[FileInfo], indent: str = "") -> str:
        """Generate tree-style output."""
        lines = []
        
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            prefix = "└── " if is_last else "├── "
            
            # File/dir marker
            if item.type == 'dir':
                marker = "[DIR] "
            elif item.type == 'symlink':
                marker = "[LINK] "
            else:
                marker = "[FILE] "
            
            # Description
            desc = f" - {item.description}" if item.description else ""
            if not item.has_metadata and item.type != 'symlink':
                desc += " ⚠️ NO METADATA"
            
            lines.append(f"{indent}{prefix}{marker}{item.name}{desc}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_json(items: List[FileInfo]) -> str:
        """Generate JSON output."""
        data = {
            'items': [asdict(item) for item in items]
        }
        return json.dumps(data, indent=2)
    
    @staticmethod
    def format_markdown(items: List[FileInfo]) -> str:
        """Generate Markdown table output."""
        lines = [
            "| Path | Type | Description |",
            "|------|------|-------------|"
        ]
        
        for item in items:
            desc = item.description or "_No metadata_"
            lines.append(f"| `{item.name}` | {item.type} | {desc} |")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_stats(stats: DirectoryStats) -> str:
        """Generate statistics report."""
        return f"""
Directory Statistics:
  Total Files: {stats.total_files}
  Total Directories: {stats.total_dirs}
  Documented Files: {stats.documented_files}
  Documented Directories: {stats.documented_dirs}
  Documentation Coverage: {stats.doc_percentage:.1f}%
"""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Discover and document directory structures with metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Documents/AI/Claude/claude_workspace
  %(prog)s . --depth 2 --format json
  %(prog)s ~/projects --include-hidden --stats-only
  %(prog)s --help-verbose  # Show file conventions guide
        """
    )
    
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory path to analyze (default: current directory)'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=3,
        help='Maximum recursion depth (default: 3)'
    )
    parser.add_argument(
        '--format',
        choices=['tree', 'json', 'markdown'],
        default='tree',
        help='Output format (default: tree)'
    )
    parser.add_argument(
        '--include-hidden',
        action='store_true',
        help='Include hidden files and directories'
    )
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        help='Exclude paths matching glob or regex (use re:pattern for regex); repeatable'
    )
    parser.add_argument(
        '--exclude-file',
        action='append',
        default=[],
        help='File containing exclude patterns, one per line (supports # comments)'
    )
    parser.add_argument(
        '--respect-gitignore',
        action='store_true',
        help='Apply .gitignore rules while scanning (best effort if git unavailable)'
    )
    parser.add_argument(
        '--only-tracked',
        action='store_true',
        help='Limit scan to git tracked files only (implies --respect-gitignore)'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Show only statistics, no structure'
    )
    parser.add_argument(
        '--help-verbose',
        action='store_true',
        help='Show file conventions guide'
    )
    
    args = parser.parse_args()
    
    # Show verbose help
    if args.help_verbose:
        conventions_path = Path(__file__).parent.parent.parent / 'readmes' / 'file_conventions.md'
        if conventions_path.exists():
            with open(conventions_path, 'r') as f:
                print(f.read())
        else:
            print(f"File conventions guide not found at: {conventions_path}")
            print("Expected location: ~/bin/python/readmes/file_conventions.md")
        return 0
    
    # Resolve path
    root_path = Path(args.path).resolve()
    if not root_path.exists():
        print(f"Error: Path does not exist: {root_path}", file=sys.stderr)
        return 1
    
    if not root_path.is_dir():
        print(f"Error: Path is not a directory: {root_path}", file=sys.stderr)
        return 1
    
    respect_gitignore = args.respect_gitignore or args.only_tracked
    exclude_patterns: List[str] = list(args.exclude)

    for exclude_file in args.exclude_file:
        exclude_file_path = Path(exclude_file).expanduser().resolve()
        exclude_patterns.extend(load_patterns_from_file(exclude_file_path))

    git_allowlist: Optional[GitAllowlist] = None
    if respect_gitignore:
        git_allowlist = build_git_allowlist(root_path, include_untracked=not args.only_tracked)
        if git_allowlist is None:
            if args.only_tracked:
                print("Error: --only-tracked requires a git repository", file=sys.stderr)
                return 1
            # Fallback to parsing .gitignore files directly (best effort)
            exclude_patterns.extend(load_gitignore_patterns(root_path, args.depth))
    
    # Scan directory
    print(f"Scanning: {root_path}", file=sys.stderr)
    discovery = DirectoryDiscovery(
        root_path=root_path,
        max_depth=args.depth,
        include_hidden=args.include_hidden,
        path_filter=PathFilter(
            root_path=root_path,
            include_hidden=args.include_hidden,
            exclude_patterns=exclude_patterns,
            git_allowlist=git_allowlist,
        ),
    )
    items = discovery.scan_directory(root_path)
    
    # Output stats
    formatter = OutputFormatter()
    print(formatter.format_stats(discovery.stats))
    
    # Output structure (unless stats-only)
    if not args.stats_only:
        print()  # Blank line
        if args.format == 'tree':
            print(formatter.format_tree(root_path, items))
        elif args.format == 'json':
            print(formatter.format_json(items))
        elif args.format == 'markdown':
            print(formatter.format_markdown(items))
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
