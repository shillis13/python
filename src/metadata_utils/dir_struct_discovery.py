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
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import yaml


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
    
    def __init__(self, max_depth: int = 3, include_hidden: bool = False):
        self.max_depth = max_depth
        self.include_hidden = include_hidden
        self.stats = DirectoryStats()
        self.extractor = MetadataExtractor()
    
    def should_process(self, path: Path) -> bool:
        """Determine if path should be processed."""
        if not self.include_hidden and path.name.startswith('.'):
            return False
        return True
    
    def scan_directory(self, root_path: Path, current_depth: int = 0) -> List[FileInfo]:
        """Recursively scan directory and extract metadata."""
        items = []
        
        if current_depth > self.max_depth:
            return items
        
        try:
            entries = sorted(root_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            
            for entry in entries:
                if not self.should_process(entry):
                    continue
                
                # Determine type
                if entry.is_symlink():
                    file_type = 'symlink'
                    target = os.readlink(str(entry))
                    description = f"→ {target}"
                    has_metadata = False
                elif entry.is_dir():
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
    
    # Scan directory
    print(f"Scanning: {root_path}", file=sys.stderr)
    discovery = DirectoryDiscovery(
        max_depth=args.depth,
        include_hidden=args.include_hidden
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
