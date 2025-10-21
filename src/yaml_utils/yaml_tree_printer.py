#!/usr/bin/env python3
"""
YAML ASCII Tree Printer

Displays YAML files as ASCII directory trees with optional value display,
filtering, and colorization. Can be used as a command-line script or imported
as a module providing the `yaml_tree_print` function.
"""

import argparse
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Union, Optional

# Assuming 'helpers' is a module in the same package or on the python path
# If this script is in yaml_utils, and helpers.py is also in yaml_utils,
# this relative import is correct.
from yaml_utils.yaml_helpers import load_yaml

# Try to import colorama for colored output
try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    _COLORS_AVAILABLE = True
except ImportError:
    # Fallback if colorama not available
    class Fore:
        RED = GREEN = BLUE = YELLOW = CYAN = MAGENTA = WHITE = RESET = ""

    class Style:
        BRIGHT = DIM = RESET_ALL = ""

    _COLORS_AVAILABLE = False


"""
Format a key with appropriate color coding
"""


def _format_key(key: str, value: Any, colors_enabled: bool) -> str:
    if not colors_enabled:
        return str(key)

    # Color code based on value type
    if isinstance(value, dict):
        return f"{Fore.BLUE}{Style.BRIGHT}{key}{Style.RESET_ALL}"
    elif isinstance(value, list):
        return f"{Fore.GREEN}{Style.BRIGHT}{key}{Style.RESET_ALL}"
    elif isinstance(value, bool):
        return f"{Fore.MAGENTA}{key}{Style.RESET_ALL}"
    elif isinstance(value, (int, float)):
        return f"{Fore.YELLOW}{key}{Style.RESET_ALL}"
    else:
        return f"{Fore.WHITE}{key}{Style.RESET_ALL}"


"""
Format a value for display with truncation and color coding
"""


def _format_value(value: Any, max_length: int, colors_enabled: bool) -> str:
    if isinstance(value, (dict, list)):
        count = len(value)
        type_name = "items" if isinstance(value, dict) else "elements"
        return f" {Style.DIM if colors_enabled else ''}({count} {type_name}){Style.RESET_ALL if colors_enabled else ''}"

    value_str = str(value)
    if len(value_str) > max_length:
        value_str = value_str[: max_length - 3] + "..."

    if not colors_enabled:
        return f" = {value_str}"

    color = Fore.WHITE
    if isinstance(value, bool):
        color = Fore.MAGENTA
    elif isinstance(value, (int, float)):
        color = Fore.YELLOW
    elif isinstance(value, str):
        color = Fore.GREEN
    elif value is None:
        color = Fore.RED

    return f" = {color}{value_str}{Style.RESET_ALL}"


"""
Internal recursive function to generate the ASCII tree representation.
"""


def _generate_tree_recursive(
    data: Any,
    show_values: bool,
    max_depth: int,
    key_filter: Optional[str],
    value_truncate: int,
    colors_enabled: bool,
    current_depth: int = 0,
    prefix: str = "",
    is_last: bool = True,
) -> str:
    if max_depth != -1 and current_depth > max_depth:
        return f"{prefix}{'└── ' if is_last else '├── '}{Style.DIM if colors_enabled else ''}[depth limit reached]{Style.RESET_ALL if colors_enabled else ''}\n"

    tree_lines = []

    if isinstance(data, dict):
        items = list(data.items())
        if key_filter:
            pattern = re.compile(key_filter, re.IGNORECASE)
            items = [(k, v) for k, v in items if pattern.search(str(k))]

        for i, (key, value) in enumerate(items):
            is_last_item = i == len(items) - 1
            connector = "└── " if is_last_item else "├── "
            next_prefix = prefix + ("    " if is_last_item else "│   ")

            key_display = _format_key(key, value, colors_enabled)
            value_display = (
                _format_value(value, value_truncate, colors_enabled)
                if show_values
                else ""
            )

            tree_lines.append(f"{prefix}{connector}{key_display}{value_display}\n")

            if isinstance(value, (dict, list)) and value:
                subtree = _generate_tree_recursive(
                    value,
                    show_values,
                    max_depth,
                    key_filter,
                    value_truncate,
                    colors_enabled,
                    current_depth + 1,
                    next_prefix,
                    True,
                )
                tree_lines.append(subtree)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            is_last_item = i == len(data) - 1
            connector = "└── " if is_last_item else "├── "
            next_prefix = prefix + ("    " if is_last_item else "│   ")

            index_display = f"{Fore.CYAN if colors_enabled else ''}[{i}]{Style.RESET_ALL if colors_enabled else ''}"
            value_display = ""
            if show_values and not isinstance(item, (dict, list)):
                value_display = _format_value(item, value_truncate, colors_enabled)

            tree_lines.append(f"{prefix}{connector}{index_display}{value_display}\n")

            if isinstance(item, (dict, list)):
                subtree = _generate_tree_recursive(
                    item,
                    show_values,
                    max_depth,
                    key_filter,
                    value_truncate,
                    colors_enabled,
                    current_depth + 1,
                    next_prefix,
                    True,
                )
                tree_lines.append(subtree)

    return "".join(tree_lines)


"""
Analyze YAML structure recursively to gather statistics.
"""


def _analyze_structure(data: Any, depth: int = 0) -> Dict[str, Any]:
    stats = {"total_keys": 0, "max_depth": depth, "types": {}}

    def count_type(value):
        type_name = type(value).__name__
        stats["types"][type_name] = stats["types"].get(type_name, 0) + 1

    if isinstance(data, dict):
        stats["total_keys"] += len(data)
        for key, value in data.items():
            count_type(value)
            if isinstance(value, (dict, list)):
                substats = _analyze_structure(value, depth + 1)
                stats["total_keys"] += substats["total_keys"]
                stats["max_depth"] = max(stats["max_depth"], substats["max_depth"])
                for dtype, count in substats["types"].items():
                    stats["types"][dtype] = stats["types"].get(dtype, 0) + count

    elif isinstance(data, list):
        for item in data:
            count_type(item)
            if isinstance(item, (dict, list)):
                substats = _analyze_structure(item, depth + 1)
                stats["total_keys"] += substats["total_keys"]
                stats["max_depth"] = max(stats["max_depth"], substats["max_depth"])
                for dtype, count in substats["types"].items():
                    stats["types"][dtype] = stats["types"].get(dtype, 0) + count

    return stats


"""
Generates an ASCII tree representation of a YAML data structure.
This is the primary importable function.

Args:
    data: The Python object (dict or list) loaded from a YAML file.
    show_values (bool): Whether to show key values.
    max_depth (int): Maximum depth to display (-1 for unlimited).
    key_filter (str): Regex pattern to filter keys.
    value_truncate (int): Maximum length for displayed values.
    use_color (bool): Whether to apply ANSI color codes to the output.
    show_stats (bool): Whether to include structure statistics at the end.

Returns:
    A string containing the formatted ASCII tree and optional stats.
"""


def yaml_tree_print(
    data: Any,
    show_values: bool = False,
    max_depth: int = -1,
    key_filter: Optional[str] = None,
    value_truncate: int = 50,
    use_color: bool = True,
    show_stats: bool = False,
) -> str:
    colors_enabled = _COLORS_AVAILABLE and use_color

    tree_output = _generate_tree_recursive(
        data, show_values, max_depth, key_filter, value_truncate, colors_enabled
    ).rstrip()

    if show_stats:
        stats = _analyze_structure(data)
        stats_lines = [
            f"\n{Style.BRIGHT if colors_enabled else ''}YAML Structure Statistics:{Style.RESET_ALL if colors_enabled else ''}",
            f"  Total keys: {stats['total_keys']}",
            f"  Maximum depth: {stats['max_depth']}",
            "  Data types:",
        ]
        for dtype, count in stats["types"].items():
            stats_lines.append(f"    {dtype}: {count}")
        tree_output += "\n" + "\n".join(stats_lines)

    return tree_output


"""
Examples:
  # Basic tree display
  python yaml_tree_printer.py config.yaml

  # Show values with limited depth
  python yaml_tree_printer.py config.yaml --show-values --max-depth 3

  # Filter keys and truncate long values
  python yaml_tree_printer.py config.yaml -v --filter "meta.*" --truncate 30

  # Include statistics
  python yaml_tree_printer.py config.yaml --stats
"""


def main():
    """Main function for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Display YAML files as ASCII directory trees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic tree display
  python yaml_tree_printer.py config.yaml

  # Show values with limited depth
  python yaml_tree_printer.py config.yaml --show-values --max-depth 3

  # Filter keys and truncate long values
  python yaml_tree_printer.py config.yaml -v --filter "meta.*" --truncate 30

  # Include statistics
  python yaml_tree_printer.py config.yaml --stats
        """,
    )

    parser.add_argument("yaml_file", type=Path, help="YAML file to display")
    parser.add_argument(
        "-v", "--show-values", action="store_true", help="Show key values"
    )
    parser.add_argument(
        "-d",
        "--max-depth",
        type=int,
        default=-1,
        help="Maximum depth to display (-1 for unlimited)",
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="key_filter",
        help="Regex pattern to filter keys (case-insensitive)",
    )
    parser.add_argument(
        "-t",
        "--truncate",
        type=int,
        default=50,
        help="Maximum length for displayed values",
    )
    parser.add_argument(
        "-s", "--stats", action="store_true", help="Show structure statistics"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )

    args = parser.parse_args()

    try:
        data = load_yaml(args.yaml_file)

        use_color_flag = not args.no_color

        print(
            f"{Style.BRIGHT if use_color_flag and _COLORS_AVAILABLE else ''}YAML Tree: {args.yaml_file}{Style.RESET_ALL if use_color_flag and _COLORS_AVAILABLE else ''}"
        )
        print("=" * 50)

        # Call the main library function to generate the output
        s = yaml_tree_print(
            data,
            show_values=args.show_values,
            max_depth=args.max_depth,
            key_filter=args.key_filter,
            value_truncate=args.truncate,
            use_color=use_color_flag,
            show_stats=args.stats,
        )

        print(tree_output)

    except Exception as e:
        print(
            f"{Fore.RED if _COLORS_AVAILABLE else ''}❌ Error: {e}{Style.RESET_ALL if _COLORS_AVAILABLE else ''}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
