#!/usr/bin/env python3

"""
JSON Chat Filter

Accepts a list of JSON chat files from stdin or command-line arguments,
applies a wide range of filters, and outputs the paths of the new, filtered
JSON files to stdout for pipeline chaining.
"""

import json
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Use the established library for handling file inputs.
try:
    from lib_fileinput import get_file_paths_from_input
except ImportError:
    from .lib_fileinput import get_file_paths_from_input

# --- Core Filtering Logic ---

"""
Parse range specification like "1-10,20,30-40,50-"

Args:
    range_spec (str): String with comma-separated ranges
    
Returns:
    set: Set of integers representing all included indices
"""


def parse_range_spec(range_spec: str) -> set:
    if not range_spec:
        return set()
    indices = set()
    for part in range_spec.split(","):
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str)
            if end_str == "":  # Open-ended range like "50-"
                indices.add(("range_open", start))
            else:  # Closed range like "1-10"
                indices.update(range(start, int(end_str) + 1))
        elif part:
            indices.add(int(part))
    return indices


"""
Expand open-ended ranges based on actual message count

Args:
    indices_set (set): Set containing indices and open range tuples
    max_index (int): Maximum message index available
    
Returns:
    set: Set of actual integer indices
"""


def expand_open_ranges(indices_set: set, max_index: int) -> set:
    expanded = set()
    for item in indices_set:
        if isinstance(item, tuple) and item[0] == "range_open":
            start = item[1]
            expanded.update(range(start, max_index + 1))
        else:
            expanded.add(item)
    return expanded


"""
Check if message contains any of the keywords

Args:
    message (Dict[str, Any]): Message object
    keywords (List[str]): List of keywords to search for
    case_sensitive (bool): Whether to match case-sensitively
    
Returns:
    bool: True if any keyword was found
"""


def message_contains_keywords(
    message: Dict[str, Any], keywords: List[str], case_sensitive: bool
) -> bool:
    if not keywords:
        return True
    content = message.get("content", "")
    if not case_sensitive:
        content = content.lower()
        keywords = [k.lower() for k in keywords]
    return any(keyword in content for keyword in keywords)


"""
Advanced message filtering with multiple criteria

Args:
    messages (List[Dict[str, Any]]): List of message objects
    config (Dict[str, Any]): Dictionary with filter configuration
    
Returns:
    Tuple[List[Dict[str, Any]], Dict[str, Any]]: Tuple of (filtered_messages, filter_stats)
"""


def filter_messages(
    messages: List[Dict[str, Any]], config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    filtered = []
    stats = {"original_count": len(messages), "filtered_count": 0}

    for i, message in enumerate(messages):
        message_index = i + 1
        include = True

        # Role filtering
        if "roles" in config and message.get("role", "").lower() not in config["roles"]:
            include = False

        # Index filtering
        if "keep_indices" in config and message_index not in expand_open_ranges(
            config["keep_indices"], len(messages)
        ):
            include = False
        if "remove_indices" in config and message_index in expand_open_ranges(
            config["remove_indices"], len(messages)
        ):
            include = False

        # Keyword filtering
        if "include_keywords" in config and not message_contains_keywords(
            message, config["include_keywords"], config.get("case_sensitive", False)
        ):
            include = False
        if "exclude_keywords" in config and message_contains_keywords(
            message, config["exclude_keywords"], config.get("case_sensitive", False)
        ):
            include = False

        # Length filtering
        content = message.get("content", "")
        if "min_length" in config and len(content) < config["min_length"]:
            include = False
        if "max_length" in config and len(content) > config["max_length"]:
            include = False

        # Word count filtering
        word_count = len(content.split())
        if "min_words" in config and word_count < config["min_words"]:
            include = False
        if "max_words" in config and word_count > config["max_words"]:
            include = False

        if include:
            msg_copy = message.copy()
            msg_copy["_original_index"] = message_index
            filtered.append(msg_copy)

    stats["filtered_count"] = len(filtered)
    return filtered, stats


# --- Analysis Functions ---

"""
Analyze JSON chat file to extract role information and statistics

Args:
    input_file (Path): Path to JSON chat file
    
Returns:
    Dict[str, Any]: Analysis results including roles, counts, and statistics
"""


def analyze_chat_file(input_file: Path) -> Dict[str, Any]:
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            chat_data = json.load(f)

        messages = chat_data.get("messages", [])

        # Count roles
        role_counts = {}
        total_chars = 0
        total_words = 0

        for message in messages:
            role = message.get("role", "unknown").lower()
            role_counts[role] = role_counts.get(role, 0) + 1

            content = message.get("content", "")
            total_chars += len(content)
            total_words += len(content.split())

        total_messages = len(messages)

        return {
            "total_messages": total_messages,
            "role_counts": role_counts,
            "available_roles": list(role_counts.keys()),
            "total_characters": total_chars,
            "total_words": total_words,
            "avg_message_length": (
                total_chars / total_messages if total_messages > 0 else 0
            ),
        }

    except Exception as e:
        print(f"❌ Error analyzing {input_file}: {e}", file=sys.stderr)
        return None


"""
Display role information for a single or multiple files

Args:
    file_paths (List[str]): List of file paths to analyze
    list_only (bool): If True, only show available roles; if False, show full stats
    
Returns:
    None
"""


def show_file_analysis(file_paths: List[str], list_only: bool = False) -> None:
    if len(file_paths) == 1:
        # Single file analysis
        input_file = Path(file_paths[0])
        analysis = analyze_chat_file(input_file)

        if not analysis:
            return

        if list_only:
            roles = ", ".join(analysis["available_roles"])
            print(f"Available roles: {roles}")
        else:
            print(f"📊 Analysis of {input_file.name}:")
            print(f"   Total messages: {analysis['total_messages']}")
            print(f"   Available roles: {', '.join(analysis['available_roles'])}")
            print(f"   Role distribution:")

            for role, count in analysis["role_counts"].items():
                percentage = (count / analysis["total_messages"]) * 100
                print(f"     {role}: {count} messages ({percentage:.1f}%)")

            print(
                f"   Average message length: {analysis['avg_message_length']:.1f} characters"
            )
            print(f"   Total words: {analysis['total_words']:,}")
    else:
        # Multiple files analysis
        all_roles = set()
        total_files = 0

        print("📊 Multi-file Analysis:")

        for file_path in file_paths:
            input_file = Path(file_path)
            analysis = analyze_chat_file(input_file)

            if analysis:
                total_files += 1
                all_roles.update(analysis["available_roles"])

                if not list_only:
                    print(f"\n   {input_file.name}:")
                    print(f"     Messages: {analysis['total_messages']}")
                    roles_str = ", ".join(analysis["available_roles"])
                    print(f"     Roles: {roles_str}")

        if list_only:
            print(
                f"All available roles across {total_files} files: {', '.join(sorted(all_roles))}"
            )
        else:
            print(f"\n   Summary: {total_files} files analyzed")
            print(f"   All roles found: {', '.join(sorted(all_roles))}")


"""
Validate and suggest corrections for user-specified roles

Args:
    requested_roles (List[str]): Roles requested by user
    available_roles (List[str]): Roles actually available in the file
    
Returns:
    Tuple[List[str], List[str]]: (valid_roles, invalid_roles)
"""


def validate_roles(
    requested_roles: List[str], available_roles: List[str]
) -> Tuple[List[str], List[str]]:
    valid_roles = []
    invalid_roles = []

    for role in requested_roles:
        if role.lower() in [r.lower() for r in available_roles]:
            valid_roles.append(role.lower())
        else:
            invalid_roles.append(role)

    return valid_roles, invalid_roles


# --- Pipeline Integration ---

"""
Generate output filename based on input file and processing

Args:
    input_file (Path): Original input file path
    output_dir (Path): Directory for output files
    
Returns:
    Path: Generated output filename with timestamp and script name
"""


def generate_output_filename(input_file: Path, output_dir: Path = None) -> Path:
    if output_dir is None:
        output_dir = input_file.parent

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = input_file.stem
    script_name = Path(__file__).stem

    output_name = f"{base_name}.{script_name}.{timestamp}.json"
    return output_dir / output_name


"""
Read, filter, and write a single JSON file

Args:
    input_file (Path): Input JSON file path
    output_file (Path): Output JSON file path
    args (argparse.Namespace): Parsed command-line arguments
    
Returns:
    bool: True if conversion successful, False otherwise
"""


def process_single_file(
    input_file: Path, output_file: Path, args: argparse.Namespace
) -> bool:
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            chat_data = json.load(f)

        messages = chat_data.get("messages", [])

        # Validate roles if specified
        if args.roles:
            analysis = analyze_chat_file(input_file)
            if analysis:
                requested_roles = [r.strip() for r in args.roles.split(",")]
                valid_roles, invalid_roles = validate_roles(
                    requested_roles, analysis["available_roles"]
                )

                if invalid_roles:
                    print(
                        f"❌ Error in {input_file.name}: Role(s) not found: {', '.join(invalid_roles)}",
                        file=sys.stderr,
                    )
                    print(
                        f"   Available roles: {', '.join(analysis['available_roles'])}",
                        file=sys.stderr,
                    )

                    # Suggest similar roles
                    for invalid_role in invalid_roles:
                        suggestions = [
                            role
                            for role in analysis["available_roles"]
                            if invalid_role.lower() in role.lower()
                            or role.lower() in invalid_role.lower()
                        ]
                        if suggestions:
                            print(
                                f"   Did you mean: {', '.join(suggestions)}?",
                                file=sys.stderr,
                            )
                    return False

        # Build filter configuration from args
        filter_config = {}
        if args.roles:
            filter_config["roles"] = [r.strip().lower() for r in args.roles.split(",")]
        if args.keep_msgs:
            filter_config["keep_indices"] = parse_range_spec(args.keep_msgs)
        if args.remove_msgs:
            filter_config["remove_indices"] = parse_range_spec(args.remove_msgs)
        if args.include_kw:
            filter_config["include_keywords"] = [
                k.strip() for k in args.include_kw.split(",")
            ]
        if args.exclude_kw:
            filter_config["exclude_keywords"] = [
                k.strip() for k in args.exclude_kw.split(",")
            ]
        if args.case_sensitive:
            filter_config["case_sensitive"] = True
        if args.min_length:
            filter_config["min_length"] = args.min_length
        if args.max_length:
            filter_config["max_length"] = args.max_length
        if args.min_words:
            filter_config["min_words"] = args.min_words
        if args.max_words:
            filter_config["max_words"] = args.max_words

        filtered_messages, stats = filter_messages(messages, filter_config)

        # Create new JSON structure
        new_data = chat_data.copy()
        new_data["messages"] = filtered_messages
        if "metadata" not in new_data:
            new_data["metadata"] = {}
        new_data["metadata"]["filter_applied"] = {
            "source_file": str(input_file),
            "filter_date": datetime.now().isoformat(),
            "filter_args": vars(args),
            "stats": stats,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)

        print(
            f"ℹ️ Filtered {input_file.name}: {stats['original_count']} -> {stats['filtered_count']} messages.",
            file=sys.stderr,
        )
        return True

    except Exception as e:
        print(f"❌ Error processing {input_file}: {e}", file=sys.stderr)
        return False


"""
Main pipeline processing loop

Args:
    args (argparse.Namespace): Parsed command-line arguments
    
Returns:
    None
"""


def process_files_pipeline(args: argparse.Namespace) -> None:
    file_paths, _ = get_file_paths_from_input(args)

    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    output_dir = Path(args.output_dir) if args.output_dir else None
    successful_ops = 0

    for file_path_str in file_paths:
        input_file = Path(file_path_str)
        output_file = generate_output_filename(input_file, output_dir)

        if process_single_file(input_file, output_file, args):
            print(str(output_file))  # Print new file path to stdout for chaining
            successful_ops += 1

    print(f"✅ Successfully processed {successful_ops} files.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Advanced filtering for ChatGPT JSON exports for pipeline usage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover available roles
    json_chat_filter.py chat.json --list-roles
    
    # Show detailed file analysis
    json_chat_filter.py chat.json --stats
    
    # Filter by roles (with validation)
    json_chat_filter.py chat.json --roles "user,assistant"
    
    # Pipeline usage
    findFiles --ext json | json_chat_filter.py --roles "user" | json_to_html.py
        """,
    )

    parser.add_argument(
        "files", nargs="*", help="Input JSON files or patterns. Omit if using stdin."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Output directory for generated files (default: same as input).",
    )
    parser.add_argument("-ff", "--from-file", help="Read file paths from a text file.")

    # Analysis options
    analysis_group = parser.add_mutually_exclusive_group()
    analysis_group.add_argument(
        "--list-roles",
        action="store_true",
        help="List available roles in the file(s) and exit.",
    )
    analysis_group.add_argument(
        "--stats", action="store_true", help="Show detailed file analysis and exit."
    )

    # Filtering arguments
    index_group = parser.add_mutually_exclusive_group()
    index_group.add_argument(
        "--keep-msgs", help='Keep specific message indices (e.g., "1-10,20,50-").'
    )
    index_group.add_argument(
        "--remove-msgs", help='Remove specific message indices (e.g., "5,10-15").'
    )
    parser.add_argument(
        "--roles", help='Comma-separated roles to keep (e.g., "user,assistant").'
    )
    parser.add_argument(
        "--include-kw", help="Comma-separated keywords to require in messages."
    )
    parser.add_argument(
        "--exclude-kw", help="Comma-separated keywords to exclude messages."
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make keyword matching case-sensitive.",
    )
    parser.add_argument(
        "--min-length", type=int, help="Minimum character length for messages."
    )
    parser.add_argument(
        "--max-length", type=int, help="Maximum character length for messages."
    )
    parser.add_argument(
        "--min-words", type=int, help="Minimum word count for messages."
    )
    parser.add_argument(
        "--max-words", type=int, help="Maximum word count for messages."
    )

    args = parser.parse_args()

    # Get file paths
    file_paths, _ = get_file_paths_from_input(args)

    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    # Handle analysis modes
    if args.list_roles or args.stats:
        show_file_analysis(file_paths, list_only=args.list_roles)
        return

    # Check that at least one filter is applied for filtering mode
    filter_args = [
        "keep_msgs",
        "remove_msgs",
        "roles",
        "include_kw",
        "exclude_kw",
        "min_length",
        "max_length",
        "min_words",
        "max_words",
    ]
    if not any(getattr(args, fa) for fa in filter_args):
        parser.error(
            "At least one filtering argument is required (e.g., --roles, --keep-msgs). Use --list-roles or --stats for analysis."
        )

    process_files_pipeline(args)


if __name__ == "__main__":
    main()
