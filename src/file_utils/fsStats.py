#!/usr/bin/env python3
"""
fsStats.py - File Statistics and Sorted Listings

Compute statistics and sorted listings from piped file paths.
Designed for pipeline use: find . -print | fsStats.py [options]

Usage:
    find . -name "*.py" | fsStats.py                    # Default stats summary
    find . -type f | fsStats.py --sort size --top 20    # Top 20 by size
    ls -1 | fsStats.py --sort modified --reverse        # Oldest first
    find . -print | fsStats.py --format json            # JSON output

Examples:
    find . -print | fsStats.py                          # Summary: counts + total size
    find . -type f -print | fsStats.py --sort size -r   # Largest files first
    find ~/Downloads -print | fsStats.py --top 10       # Top 10 largest
    find . -name "*.log" | fsStats.py --total-only      # Just the total size
    find . -print | fsStats.py --histogram              # Size distribution
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Import from existing file_utils where possible
try:
    from file_utils.lib_fileinput import get_file_paths_from_input, _normalize_input_path
except ImportError:
    # Fallback if run standalone
    def _normalize_input_path(raw_path: str) -> str:
        cleaned = raw_path.strip().strip('"').strip("'")
        if not cleaned:
            return cleaned
        path = Path(cleaned).expanduser()
        try:
            path = path.resolve(strict=False)
        except OSError:
            pass
        return str(path)


@dataclass
class FileStats:
    """Statistics for a single file or directory."""
    path: Path
    name: str
    is_dir: bool
    is_file: bool
    is_symlink: bool
    size: int = 0
    modified: Optional[datetime] = None
    created: Optional[datetime] = None
    accessed: Optional[datetime] = None
    extension: str = ""
    
    @classmethod
    def from_path(cls, path_str: str) -> Optional['FileStats']:
        """Create FileStats from path string, returns None if path doesn't exist."""
        path = Path(path_str)
        if not path.exists():
            return None
        
        stats = cls(
            path=path,
            name=path.name,
            is_dir=path.is_dir(),
            is_file=path.is_file(),
            is_symlink=path.is_symlink(),
            extension="".join(path.suffixes).lstrip(".").lower()
        )
        
        try:
            stat_info = path.stat()
            if stats.is_file:
                stats.size = stat_info.st_size
            stats.modified = datetime.fromtimestamp(stat_info.st_mtime)
            stats.created = datetime.fromtimestamp(stat_info.st_ctime)
            stats.accessed = datetime.fromtimestamp(stat_info.st_atime)
        except (OSError, PermissionError):
            pass
        
        return stats
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.name,
            "type": "dir" if self.is_dir else ("symlink" if self.is_symlink else "file"),
            "size": self.size,
            "modified": self.modified.isoformat() if self.modified else None,
            "created": self.created.isoformat() if self.created else None,
            "extension": self.extension,
        }


@dataclass
class AggregateStats:
    """Aggregate statistics across all files."""
    file_count: int = 0
    dir_count: int = 0
    symlink_count: int = 0
    total_size: int = 0
    smallest_file: Optional[FileStats] = None
    largest_file: Optional[FileStats] = None
    oldest_modified: Optional[FileStats] = None
    newest_modified: Optional[FileStats] = None
    oldest_created: Optional[FileStats] = None
    newest_created: Optional[FileStats] = None
    extensions: Dict[str, int] = field(default_factory=dict)
    size_buckets: Dict[str, int] = field(default_factory=dict)
    
    def update(self, fs: FileStats) -> None:
        """Update aggregate stats with a new file."""
        if fs.is_dir:
            self.dir_count += 1
        elif fs.is_symlink:
            self.symlink_count += 1
        else:
            self.file_count += 1
            self.total_size += fs.size
            
            # Track smallest/largest
            if self.smallest_file is None or fs.size < self.smallest_file.size:
                self.smallest_file = fs
            if self.largest_file is None or fs.size > self.largest_file.size:
                self.largest_file = fs
            
            # Track extension counts
            ext = fs.extension or "(no ext)"
            self.extensions[ext] = self.extensions.get(ext, 0) + 1
            
            # Track size distribution
            bucket = self._size_bucket(fs.size)
            self.size_buckets[bucket] = self.size_buckets.get(bucket, 0) + 1
        
        # Track oldest/newest by modification date
        if fs.modified:
            if self.oldest_modified is None or fs.modified < self.oldest_modified.modified:
                self.oldest_modified = fs
            if self.newest_modified is None or fs.modified > self.newest_modified.modified:
                self.newest_modified = fs
        
        # Track oldest/newest by creation date
        if fs.created:
            if self.oldest_created is None or fs.created < self.oldest_created.created:
                self.oldest_created = fs
            if self.newest_created is None or fs.created > self.newest_created.created:
                self.newest_created = fs
    
    def _size_bucket(self, size: int) -> str:
        """Categorize size into buckets."""
        if size == 0:
            return "0 (empty)"
        elif size < 1024:
            return "< 1K"
        elif size < 10 * 1024:
            return "1K - 10K"
        elif size < 100 * 1024:
            return "10K - 100K"
        elif size < 1024 * 1024:
            return "100K - 1M"
        elif size < 10 * 1024 * 1024:
            return "1M - 10M"
        elif size < 100 * 1024 * 1024:
            return "10M - 100M"
        elif size < 1024 * 1024 * 1024:
            return "100M - 1G"
        else:
            return "> 1G"


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    for unit in ["B", "K", "M", "G", "T"]:
        if size < 1024:
            if unit == "B":
                return f"{size}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}P"


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def read_paths_from_stdin() -> List[str]:
    """Read file paths from stdin, one per line."""
    paths = []
    if sys.stdin.isatty():
        return paths
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        paths.append(_normalize_input_path(line))
    
    return paths


def collect_stats(paths: List[str]) -> Tuple[List[FileStats], AggregateStats]:
    """Collect statistics for all paths."""
    items: List[FileStats] = []
    agg = AggregateStats()
    
    for path_str in paths:
        fs = FileStats.from_path(path_str)
        if fs:
            items.append(fs)
            agg.update(fs)
    
    return items, agg


def sort_items(items: List[FileStats], sort_key: str, reverse: bool = True) -> List[FileStats]:
    """Sort items by specified key."""
    def get_sort_value(fs: FileStats):
        if sort_key == "size":
            return fs.size
        elif sort_key == "modified":
            return fs.modified.timestamp() if fs.modified else 0
        elif sort_key == "created":
            return fs.created.timestamp() if fs.created else 0
        elif sort_key == "accessed":
            return fs.accessed.timestamp() if fs.accessed else 0
        elif sort_key == "extension":
            return (fs.extension or "zzz", fs.name.lower())  # no ext sorts last
        else:  # name
            return fs.name.lower()
    
    return sorted(items, key=get_sort_value, reverse=reverse)


def format_summary(agg: AggregateStats, verbose: bool = False) -> str:
    """Format aggregate statistics summary."""
    lines = []
    lines.append("=" * 50)
    lines.append("FILE STATISTICS SUMMARY")
    lines.append("=" * 50)
    
    # Counts
    total_items = agg.file_count + agg.dir_count + agg.symlink_count
    lines.append(f"Total items:      {total_items:,}")
    lines.append(f"  Files:          {agg.file_count:,}")
    lines.append(f"  Directories:    {agg.dir_count:,}")
    if agg.symlink_count > 0:
        lines.append(f"  Symlinks:       {agg.symlink_count:,}")
    
    lines.append("")
    
    # Size info
    lines.append(f"Total size:       {format_size(agg.total_size)} ({agg.total_size:,} bytes)")
    if agg.file_count > 0:
        avg_size = agg.total_size // agg.file_count
        lines.append(f"Average size:     {format_size(avg_size)}")
    
    if agg.smallest_file and agg.largest_file:
        lines.append("")
        lines.append(f"Smallest:         {format_size(agg.smallest_file.size):>8}  {agg.smallest_file.name}")
        lines.append(f"Largest:          {format_size(agg.largest_file.size):>8}  {agg.largest_file.name}")
    
    # Date info
    if agg.oldest_modified and agg.newest_modified:
        lines.append("")
        lines.append(f"Oldest modified:  {format_datetime(agg.oldest_modified.modified)}  {agg.oldest_modified.name}")
        lines.append(f"Newest modified:  {format_datetime(agg.newest_modified.modified)}  {agg.newest_modified.name}")
    
    if verbose:
        # Size distribution
        if agg.size_buckets:
            lines.append("")
            lines.append("Size Distribution:")
            bucket_order = [
                "0 (empty)", "< 1K", "1K - 10K", "10K - 100K",
                "100K - 1M", "1M - 10M", "10M - 100M", "100M - 1G", "> 1G"
            ]
            for bucket in bucket_order:
                if bucket in agg.size_buckets:
                    count = agg.size_buckets[bucket]
                    pct = (count / agg.file_count * 100) if agg.file_count > 0 else 0
                    bar = "█" * int(pct / 2)
                    lines.append(f"  {bucket:>12}: {count:>6} ({pct:>5.1f}%) {bar}")
        
        # Top extensions
        if agg.extensions:
            lines.append("")
            lines.append("Top Extensions:")
            sorted_exts = sorted(agg.extensions.items(), key=lambda x: x[1], reverse=True)[:10]
            for ext, count in sorted_exts:
                pct = (count / agg.file_count * 100) if agg.file_count > 0 else 0
                lines.append(f"  .{ext:>10}: {count:>6} ({pct:>5.1f}%)")
    
    lines.append("=" * 50)
    return "\n".join(lines)


def format_list(items: List[FileStats], columns: List[str], limit: Optional[int] = None) -> str:
    """Format items as a list with specified columns."""
    if limit:
        items = items[:limit]
    
    if not items:
        return "No items to display."
    
    lines = []
    
    # Build header
    col_widths = {
        "size": 10,
        "modified": 19,
        "created": 19,
        "accessed": 19,
        "extension": 8,
        "type": 6,
    }
    
    for item in items:
        parts = []
        for col in columns:
            if col == "size":
                parts.append(f"{format_size(item.size):>10}")
            elif col == "modified":
                parts.append(f"{format_datetime(item.modified):>19}")
            elif col == "created":
                parts.append(f"{format_datetime(item.created):>19}")
            elif col == "accessed":
                parts.append(f"{format_datetime(item.accessed):>19}")
            elif col == "extension":
                parts.append(f"{item.extension:>8}")
            elif col == "type":
                t = "dir" if item.is_dir else ("sym" if item.is_symlink else "file")
                parts.append(f"{t:>6}")
            elif col == "path":
                parts.append(str(item.path))
            else:  # name
                parts.append(item.name)
        
        lines.append("  ".join(parts))
    
    return "\n".join(lines)


def format_json(items: List[FileStats], agg: AggregateStats, include_items: bool = True) -> str:
    """Format as JSON."""
    data = {
        "summary": {
            "file_count": agg.file_count,
            "dir_count": agg.dir_count,
            "symlink_count": agg.symlink_count,
            "total_items": agg.file_count + agg.dir_count + agg.symlink_count,
            "total_size": agg.total_size,
            "total_size_formatted": format_size(agg.total_size),
            "average_size": agg.total_size // agg.file_count if agg.file_count > 0 else 0,
            "extensions": agg.extensions,
            "size_distribution": agg.size_buckets,
        }
    }
    
    if agg.smallest_file:
        data["summary"]["smallest"] = {"path": str(agg.smallest_file.path), "size": agg.smallest_file.size}
    if agg.largest_file:
        data["summary"]["largest"] = {"path": str(agg.largest_file.path), "size": agg.largest_file.size}
    if agg.oldest_modified:
        data["summary"]["oldest_modified"] = {"path": str(agg.oldest_modified.path), "date": format_datetime(agg.oldest_modified.modified)}
    if agg.newest_modified:
        data["summary"]["newest_modified"] = {"path": str(agg.newest_modified.path), "date": format_datetime(agg.newest_modified.modified)}
    
    if include_items:
        data["items"] = [fs.to_dict() for fs in items]
    
    return json.dumps(data, indent=2)


def format_histogram(agg: AggregateStats, width: int = 40) -> str:
    """Format size distribution as ASCII histogram."""
    if not agg.size_buckets or agg.file_count == 0:
        return "No files to display histogram."
    
    lines = []
    lines.append("Size Distribution Histogram")
    lines.append("-" * (width + 25))
    
    bucket_order = [
        "0 (empty)", "< 1K", "1K - 10K", "10K - 100K",
        "100K - 1M", "1M - 10M", "10M - 100M", "100M - 1G", "> 1G"
    ]
    
    max_count = max(agg.size_buckets.values()) if agg.size_buckets else 1
    
    for bucket in bucket_order:
        count = agg.size_buckets.get(bucket, 0)
        if count > 0:
            bar_len = int((count / max_count) * width)
            bar = "█" * bar_len
            pct = count / agg.file_count * 100
            lines.append(f"{bucket:>12} │ {bar:<{width}} │ {count:>6} ({pct:>5.1f}%)")
    
    lines.append("-" * (width + 25))
    return "\n".join(lines)


def format_extensions(agg: AggregateStats, limit: int = 20) -> str:
    """Format extension breakdown."""
    if not agg.extensions:
        return "No extensions to display."
    
    lines = []
    lines.append("Extension Breakdown")
    lines.append("-" * 40)
    
    sorted_exts = sorted(agg.extensions.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    for ext, count in sorted_exts:
        pct = count / agg.file_count * 100 if agg.file_count > 0 else 0
        bar = "█" * int(pct / 2)
        lines.append(f".{ext:>10}: {count:>6} ({pct:>5.1f}%) {bar}")
    
    if len(agg.extensions) > limit:
        remaining = len(agg.extensions) - limit
        lines.append(f"  ... and {remaining} more extensions")
    
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compute file statistics from piped input.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  find . -print | fsStats.py                    # Summary stats
  find . -type f | fsStats.py --sort size -r    # Largest files first
  find . -print | fsStats.py --top 20           # Top 20 by size
  find . -print | fsStats.py --histogram        # Size distribution
  find . -print | fsStats.py --extensions       # Extension breakdown
  find . -print | fsStats.py --total-only       # Just total size
  find . -print | fsStats.py --format json      # JSON output
  find . -print | fsStats.py -v                 # Verbose summary
"""
    )
    
    # Input options
    parser.add_argument(
        "paths", nargs="*",
        help="Additional paths (primarily for testing; stdin is primary input)"
    )
    
    # Output mode
    mode_group = parser.add_argument_group("Output Mode")
    mode_group.add_argument(
        "--summary", "-s", action="store_true", default=True,
        help="Show summary statistics (default)"
    )
    mode_group.add_argument(
        "--list", "-l", action="store_true",
        help="List files with stats"
    )
    mode_group.add_argument(
        "--histogram", "-H", action="store_true",
        help="Show size distribution histogram"
    )
    mode_group.add_argument(
        "--extensions", "-e", action="store_true",
        help="Show extension breakdown"
    )
    mode_group.add_argument(
        "--total-only", "-t", action="store_true",
        help="Output only total size in bytes (machine-readable)"
    )
    mode_group.add_argument(
        "--total-human", "-T", action="store_true",
        help="Output only total size in human-readable format (e.g., 1.5G)"
    )
    mode_group.add_argument(
        "--count-only", "-c", action="store_true",
        help="Output only counts (files dirs symlinks total)"
    )
    
    # Sorting
    sort_group = parser.add_argument_group("Sorting (for --list)")
    sort_group.add_argument(
        "--sort", choices=["name", "size", "modified", "created", "accessed", "extension"],
        default="size",
        help="Sort key (default: size)"
    )
    sort_group.add_argument(
        "--reverse", "-r", action="store_true", default=True,
        help="Reverse sort (default: True for size, showing largest first)"
    )
    sort_group.add_argument(
        "--no-reverse", action="store_false", dest="reverse",
        help="Don't reverse sort (smallest/oldest first)"
    )
    
    # Filtering/limiting
    filter_group = parser.add_argument_group("Filtering")
    filter_group.add_argument(
        "--top", "-n", type=int, metavar="N",
        help="Show only top N items"
    )
    filter_group.add_argument(
        "--files-only", "-f", action="store_true",
        help="Only include files (not directories)"
    )
    filter_group.add_argument(
        "--dirs-only", "-d", action="store_true",
        help="Only include directories"
    )
    
    # Output format
    format_group = parser.add_argument_group("Output Format")
    format_group.add_argument(
        "--format", choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)"
    )
    format_group.add_argument(
        "--columns", 
        default="size,modified,path",
        help="Columns for list output (default: size,modified,path)"
    )
    format_group.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output (include distributions in summary)"
    )
    format_group.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress headers and formatting"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Collect paths from stdin
    paths = read_paths_from_stdin()
    
    # Add any command-line paths (primarily for testing)
    if args.paths:
        for p in args.paths:
            paths.append(_normalize_input_path(p))
    
    if not paths:
        if sys.stdin.isatty():
            print("Usage: find . -print | fsStats.py [options]", file=sys.stderr)
            print("       fsStats.py --help for more info", file=sys.stderr)
            sys.exit(1)
        else:
            # Empty input from pipe is valid, just nothing to process
            if args.total_only:
                print("0")
            elif args.total_human:
                print("0B")
            elif args.count_only:
                print("0 0 0 0")  # files dirs symlinks total
            elif not args.quiet:
                print("No input received.", file=sys.stderr)
            sys.exit(0)
    
    # Collect stats
    items, agg = collect_stats(paths)
    
    # Filter if requested
    if args.files_only:
        items = [fs for fs in items if fs.is_file]
    elif args.dirs_only:
        items = [fs for fs in items if fs.is_dir]
    
    # Sort
    items = sort_items(items, args.sort, args.reverse)
    
    # Output based on mode
    if args.total_only:
        print(agg.total_size)
    
    elif args.total_human:
        print(format_size(agg.total_size))
    
    elif args.count_only:
        total = agg.file_count + agg.dir_count + agg.symlink_count
        print(f"{agg.file_count} {agg.dir_count} {agg.symlink_count} {total}")
    
    elif args.format == "json":
        include_items = args.list or args.top is not None
        if args.top:
            items = items[:args.top]
        print(format_json(items, agg, include_items=include_items))
    
    elif args.list:
        columns = [c.strip() for c in args.columns.split(",")]
        print(format_list(items, columns, limit=args.top))
        if not args.quiet:
            print()
            print(f"Total: {agg.file_count} files, {agg.dir_count} dirs, {format_size(agg.total_size)}", file=sys.stderr)
    
    elif args.histogram:
        print(format_histogram(agg))
    
    elif args.extensions:
        print(format_extensions(agg, limit=args.top or 20))
    
    else:
        # Default: summary
        print(format_summary(agg, verbose=args.verbose))


if __name__ == "__main__":
    main()
