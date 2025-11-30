#!/usr/bin/env python3
"""
chat_pipeline_runner.py - Orchestrates the full chat history pipeline

Pipeline Stages:
  _incoming/       → Raw drops (zips, exports) - MANUAL
  10_exported/     → Unzipped/copied, ready for processing
  20_preprocessed/ → Split, cleaned, normalized
  30_converted/    → Standard YAML format
  40_histories/    → Chunked, organized by AI/date/chat_id

Usage:
  python chat_pipeline_runner.py --stage all        # Run full pipeline
  python chat_pipeline_runner.py --stage unpack     # Just unpack incoming
  python chat_pipeline_runner.py --stage preprocess # Just preprocess
  python chat_pipeline_runner.py --stage convert    # Just convert
  python chat_pipeline_runner.py --stage chunk      # Just chunk
  python chat_pipeline_runner.py --dry-run          # Show what would happen
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

AI_MEMORIES_ROOT = Path.home() / "Documents/AI/ai_root/ai_memories"

DIRS = {
    "incoming":     AI_MEMORIES_ROOT / "_incoming",
    "exported":     AI_MEMORIES_ROOT / "10_exported",
    "preprocessed": AI_MEMORIES_ROOT / "20_preprocessed",
    "converted":    AI_MEMORIES_ROOT / "30_converted",
    "histories":    AI_MEMORIES_ROOT / "40_histories",
}

# Tools location
TOOLS_ROOT = Path.home() / "bin/python/src/ai_utils"
CHAT_PROCESSING = TOOLS_ROOT / "chat_processing"
CHAT_PIPELINE = TOOLS_ROOT / "chat_pipeline"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# =============================================================================
# STAGE 1: UNPACK (_incoming → 10_exported)
# =============================================================================

def stage_unpack(dry_run: bool = False) -> int:
    """
    Unpack zip files and copy raw exports from _incoming to 10_exported.
    
    Handles:
    - .zip files → extract
    - .json files → copy (ChatGPT/Claude exports)
    - .md files → copy
    - .html files → copy
    - directories → copy recursively
    
    Returns count of items processed.
    """
    log.info("=== STAGE 1: UNPACK ===")
    incoming = DIRS["incoming"]
    exported = DIRS["exported"]
    
    if not incoming.exists():
        log.warning(f"Incoming directory does not exist: {incoming}")
        return 0
    
    count = 0
    for item in incoming.iterdir():
        if item.name.startswith('.'):
            continue
            
        log.info(f"  Processing: {item.name}")
        
        if dry_run:
            log.info(f"    [DRY RUN] Would process {item}")
            count += 1
            continue
            
        # TODO: Implement actual unpacking logic
        # - zip files: extract with zipfile module
        # - json/md/html: shutil.copy to exported/
        # - directories: shutil.copytree
        # - After successful copy, move original to _incoming/processed/
        
        count += 1
    
    log.info(f"  Unpacked {count} items")
    return count


# =============================================================================
# STAGE 2: PREPROCESS (10_exported → 20_preprocessed)
# =============================================================================

def stage_preprocess(dry_run: bool = False) -> int:
    """
    Clean and normalize exported files.
    
    Tasks:
    - Split multi-chat exports into individual files
    - Fix escaped newlines (\\n → actual newlines)
    - Expand one-liner JSON to readable format
    - Detect and tag source format (ChatGPT native, Claude, etc.)
    - Generate metadata sidecar files
    
    Uses: chat_export_splitter.py, detect_source.py
    """
    log.info("=== STAGE 2: PREPROCESS ===")
    exported = DIRS["exported"]
    preprocessed = DIRS["preprocessed"]
    
    if not exported.exists():
        log.warning(f"Exported directory does not exist: {exported}")
        return 0
    
    count = 0
    for item in exported.iterdir():
        if item.name.startswith('.') or item.name == 'processed':
            continue
            
        log.info(f"  Processing: {item.name}")
        
        if dry_run:
            log.info(f"    [DRY RUN] Would preprocess {item}")
            count += 1
            continue
        
        # TODO: Implement preprocessing
        # - Use chat_export_splitter.py for multi-chat files
        # - Use detect_source.py to identify format
        # - Normalize file structure
        # - Move processed files to preprocessed/
        # - Move originals to exported/processed/
        
        count += 1
    
    log.info(f"  Preprocessed {count} items")
    return count


# =============================================================================
# STAGE 3: CONVERT (20_preprocessed → 30_converted)
# =============================================================================

def stage_convert(dry_run: bool = False) -> int:
    """
    Convert all formats to standard YAML.
    
    Input formats supported:
    - ChatGPT native JSON export
    - ChatGPT HTML export
    - Claude JSON export
    - Markdown chat logs
    
    Output: Standardized YAML per chat_history_v2.0.schema.yaml
    
    Uses: chat_converter.py, lib_parsers/, lib_converters/
    """
    log.info("=== STAGE 3: CONVERT ===")
    preprocessed = DIRS["preprocessed"]
    converted = DIRS["converted"]
    
    if not preprocessed.exists():
        log.warning(f"Preprocessed directory does not exist: {preprocessed}")
        return 0
    
    count = 0
    for item in preprocessed.iterdir():
        if item.name.startswith('.') or item.name == 'processed':
            continue
            
        log.info(f"  Converting: {item.name}")
        
        if dry_run:
            log.info(f"    [DRY RUN] Would convert {item}")
            count += 1
            continue
        
        # TODO: Implement conversion
        # - Detect input format from metadata or extension
        # - Select appropriate parser (json_parser, html_parser, etc.)
        # - Convert to standard schema
        # - Validate against chat_history_v2.0.schema.yaml
        # - Write to converted/ with .yaml extension
        # - Move originals to preprocessed/processed/
        
        count += 1
    
    log.info(f"  Converted {count} items")
    return count


# =============================================================================
# STAGE 4: CHUNK (30_converted → 40_histories)
# =============================================================================

def stage_chunk(dry_run: bool = False) -> int:
    """
    Chunk converted chats and organize into final structure.
    
    Organization: 40_histories/{ai}/{YYYY}/{MM}/{DD}/{chat_id}/
    
    Output per chat:
    - chat.yaml      - Full chunked conversation
    - meta.yaml      - Metadata and provenance
    - chat.md        - Human-readable markdown
    - extracts/      - Extracted context (future)
    
    Uses: chat_chunker.py, process.py
    """
    log.info("=== STAGE 4: CHUNK ===")
    converted = DIRS["converted"]
    histories = DIRS["histories"]
    
    if not converted.exists():
        log.warning(f"Converted directory does not exist: {converted}")
        return 0
    
    count = 0
    for item in converted.glob("*.yaml"):
        if item.name.startswith('.'):
            continue
            
        log.info(f"  Chunking: {item.name}")
        
        if dry_run:
            log.info(f"    [DRY RUN] Would chunk {item}")
            count += 1
            continue
        
        # TODO: Implement chunking
        # - Parse YAML to extract metadata (ai, created_date, chat_id)
        # - Create target directory: histories/{ai}/{YYYY}/{MM}/{DD}/{chat_id}/
        # - Run chat_chunker.py to split into chunks
        # - Generate meta.yaml with provenance
        # - Generate chat.md markdown version
        # - Create empty extracts/ directory
        # - Move original to converted/processed/
        
        count += 1
    
    log.info(f"  Chunked {count} items")
    return count


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_pipeline(stages: list[str], dry_run: bool = False):
    """Run specified pipeline stages in order."""
    
    log.info("=" * 60)
    log.info("CHAT HISTORY PIPELINE")
    log.info(f"  Stages: {', '.join(stages)}")
    log.info(f"  Dry run: {dry_run}")
    log.info(f"  Root: {AI_MEMORIES_ROOT}")
    log.info("=" * 60)
    
    # Validate directories exist
    for name, path in DIRS.items():
        if not path.exists():
            log.warning(f"Creating missing directory: {path}")
            if not dry_run:
                path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    if "unpack" in stages or "all" in stages:
        results["unpack"] = stage_unpack(dry_run)
    
    if "preprocess" in stages or "all" in stages:
        results["preprocess"] = stage_preprocess(dry_run)
    
    if "convert" in stages or "all" in stages:
        results["convert"] = stage_convert(dry_run)
    
    if "chunk" in stages or "all" in stages:
        results["chunk"] = stage_chunk(dry_run)
    
    # Summary
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    for stage, count in results.items():
        log.info(f"  {stage}: {count} items")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate chat history pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--stage", "-s",
        choices=["all", "unpack", "preprocess", "convert", "chunk"],
        default="all",
        help="Stage(s) to run"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would happen without making changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    stages = [args.stage] if args.stage != "all" else ["unpack", "preprocess", "convert", "chunk"]
    run_pipeline(stages, args.dry_run)


if __name__ == "__main__":
    main()
