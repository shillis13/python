#!/usr/bin/env python3
"""
Gemini File Upload Preparation Script
Prepares VBA files for upload to Gemini's 1M context window

Usage:
    python gemini_prepare_upload.py <source_dir> [--output combined.txt] [--exclude "*_Tmp*,wb_*"]
    
This creates a single text file with all VBA code, formatted for Gemini analysis.
"""
import argparse
import re
from pathlib import Path
from datetime import datetime

def should_exclude(filename: str, patterns: list) -> bool:
    """Check if file matches any exclusion pattern"""
    for pattern in patterns:
        if re.match(pattern.replace('*', '.*'), filename, re.IGNORECASE):
            return True
    return False

def prepare_files(source_dir: str, output_file: str, exclude_patterns: list):
    """Combine VBA files into single file for Gemini upload"""
    
    path = Path(source_dir)
    output = Path(output_file)
    
    # Collect files
    files = []
    for ext in ['*.bas', '*.cls']:
        for f in sorted(path.glob(ext)):
            if not should_exclude(f.name, exclude_patterns):
                files.append(f)
    
    # Stats
    total_lines = 0
    total_chars = 0
    
    with output.open('w', encoding='utf-8') as out:
        # Header
        out.write(f"# VBA Framework Code Export\n")
        out.write(f"# Generated: {datetime.now().isoformat()}\n")
        out.write(f"# Source: {source_dir}\n")
        out.write(f"# Files: {len(files)}\n")
        out.write(f"# Excluded patterns: {', '.join(exclude_patterns)}\n")
        out.write("\n" + "=" * 80 + "\n\n")
        
        # Table of contents
        out.write("## TABLE OF CONTENTS\n\n")
        for i, f in enumerate(files, 1):
            content = f.read_text(encoding='utf-8', errors='ignore')
            lines = len(content.splitlines())
            match = re.search(r'Attribute VB_Name = "([^"]+)"', content)
            name = match.group(1) if match else f.stem
            out.write(f"{i:3}. {name} ({f.suffix[1:]}) - {lines} lines\n")
        out.write("\n" + "=" * 80 + "\n\n")
        
        # File contents
        for f in files:
            content = f.read_text(encoding='utf-8', errors='ignore')
            lines = len(content.splitlines())
            total_lines += lines
            total_chars += len(content)
            
            match = re.search(r'Attribute VB_Name = "([^"]+)"', content)
            name = match.group(1) if match else f.stem
            
            out.write(f"\n{'#' * 80}\n")
            out.write(f"## FILE: {name} ({f.name})\n")
            out.write(f"## Lines: {lines}\n")
            out.write(f"{'#' * 80}\n\n")
            out.write(content)
            out.write("\n\n")
    
    # Estimate tokens (rough: 4 chars per token)
    est_tokens = total_chars // 4
    
    print(f"Created: {output}")
    print(f"  Files: {len(files)}")
    print(f"  Lines: {total_lines:,}")
    print(f"  Characters: {total_chars:,}")
    print(f"  Estimated tokens: ~{est_tokens:,}")
    print(f"\nGemini 1M context: {est_tokens/1_000_000*100:.1f}% of capacity")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare VBA files for Gemini upload")
    parser.add_argument("source_dir", help="Directory containing VBA files")
    parser.add_argument("--output", "-o", default="vba_for_gemini.txt", help="Output file")
    parser.add_argument("--exclude", "-e", default="*_Tmp*,wb_*,modArraySupport*,Sheet*",
                       help="Comma-separated exclusion patterns")
    
    args = parser.parse_args()
    exclude = [p.strip() for p in args.exclude.split(',')]
    
    prepare_files(args.source_dir, args.output, exclude)
