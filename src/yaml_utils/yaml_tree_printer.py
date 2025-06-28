#!/usr/bin/env python3
"""
YAML ASCII Tree Printer

Displays YAML files as ASCII directory trees with optional value display,
filtering, and colorization.
"""

import argparse
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Union, Optional
from helpers import load_yaml

# Try to import colorama for colored output
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    # Fallback if colorama not available
    class Fore:
        RED = GREEN = BLUE = YELLOW = CYAN = MAGENTA = WHITE = RESET = ""
    
    class Style:
        BRIGHT = DIM = RESET_ALL = ""
    
    COLORS_AVAILABLE = False

"""
Generate ASCII tree representation of YAML data

Args:
    data: YAML data structure to display
    show_values (bool): Whether to show key values
    max_depth (int): Maximum depth to display (-1 for unlimited)
    current_depth (int): Current recursion depth
    prefix (str): Current line prefix for tree structure
    is_last (bool): Whether this is the last item at current level
    key_filter (str): Regex pattern to filter keys
    value_truncate (int): Maximum length for displayed values
    
Returns:
    str: ASCII tree representation
"""
def generate_tree(
    data: Any,
    show_values: bool = False,
    max_depth: int = -1,
    current_depth: int = 0,
    prefix: str = "",
    is_last: bool = True,
    key_filter: Optional[str] = None,
    value_truncate: int = 50
) -> str:
    
    if max_depth != -1 and current_depth > max_depth:
        return f"{prefix}{'└── ' if is_last else '├── '}{Style.DIM}[depth limit reached]{Style.RESET_ALL}\n"
    
    tree_lines = []
    
    if isinstance(data, dict):
        items = list(data.items())
        
        # Filter keys if pattern provided
        if key_filter:
            pattern = re.compile(key_filter, re.IGNORECASE)
            items = [(k, v) for k, v in items if pattern.search(str(k))]
        
        for i, (key, value) in enumerate(items):
            is_last_item = (i == len(items) - 1)
            
            # Choose appropriate tree symbols
            connector = "└── " if is_last_item else "├── "
            next_prefix = prefix + ("    " if is_last_item else "│   ")
            
            # Format the key with color
            key_display = format_key(key, value)
            
            # Add value if requested
            value_display = ""
            if show_values:
                value_display = format_value(value, value_truncate)
            
            tree_lines.append(f"{prefix}{connector}{key_display}{value_display}\n")
            
            # Recurse for nested structures
            if isinstance(value, (dict, list)) and value:
                subtree = generate_tree(
                    value,
                    show_values,
                    max_depth,
                    current_depth + 1,
                    next_prefix,
                    True,
                    key_filter,
                    value_truncate
                )
                tree_lines.append(subtree)
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            is_last_item = (i == len(data) - 1)
            connector = "└── " if is_last_item else "├── "
            next_prefix = prefix + ("    " if is_last_item else "│   ")
            
            # Format list index
            index_display = f"{Fore.CYAN}[{i}]{Style.RESET_ALL}"
            
            # Add value if requested and item is simple
            value_display = ""
            if show_values and not isinstance(item, (dict, list)):
                value_display = format_value(item, value_truncate)
            
            tree_lines.append(f"{prefix}{connector}{index_display}{value_display}\n")
            
            # Recurse for nested structures
            if isinstance(item, (dict, list)):
                subtree = generate_tree(
                    item,
                    show_values,
                    max_depth,
                    current_depth + 1,
                    next_prefix,
                    True,
                    key_filter,
                    value_truncate
                )
                tree_lines.append(subtree)
    
    return "".join(tree_lines)

"""
Format a key with appropriate color coding

Args:
    key: The key to format
    value: The value associated with the key
    
Returns:
    str: Formatted key string
"""
def format_key(key: str, value: Any) -> str:
    if not COLORS_AVAILABLE:
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

Args:
    value: The value to format
    max_length: Maximum length before truncation
    
Returns:
    str: Formatted value string
"""
def format_value(value: Any, max_length: int = 50) -> str:
    if isinstance(value, (dict, list)):
        count = len(value)
        type_name = "items" if isinstance(value, dict) else "elements"
        return f" {Style.DIM}({count} {type_name}){Style.RESET_ALL}"
    
    # Convert value to string
    value_str = str(value)
    
    # Truncate if too long
    if len(value_str) > max_length:
        value_str = value_str[:max_length-3] + "..."
    
    # Color code by type
    if not COLORS_AVAILABLE:
        return f" = {value_str}"
    
    if isinstance(value, bool):
        color = Fore.MAGENTA
    elif isinstance(value, (int, float)):
        color = Fore.YELLOW
    elif isinstance(value, str):
        color = Fore.GREEN
    elif value is None:
        color = Fore.RED
    else:
        color = Fore.WHITE
    
    return f" = {color}{value_str}{Style.RESET_ALL}"

"""
Print basic statistics about the YAML structure

Args:
    data: YAML data to analyze
    
Returns:
    None
"""
def print_stats(data: Any) -> None:
    stats = analyze_structure(data)
    
    print(f"\n{Style.BRIGHT}YAML Structure Statistics:{Style.RESET_ALL}")
    print(f"  Total keys: {stats['total_keys']}")
    print(f"  Maximum depth: {stats['max_depth']}")
    print(f"  Data types:")
    for dtype, count in stats['types'].items():
        print(f"    {dtype}: {count}")

"""
Analyze YAML structure recursively

Args:
    data: YAML data to analyze
    depth: Current depth (for internal recursion)
    
Returns:
    Dict: Statistics about the structure
"""
def analyze_structure(data: Any, depth: int = 0) -> Dict[str, Any]:
    stats = {
        'total_keys': 0,
        'max_depth': depth,
        'types': {}
    }
    
    def count_type(value):
        type_name = type(value).__name__
        stats['types'][type_name] = stats['types'].get(type_name, 0) + 1
    
    if isinstance(data, dict):
        stats['total_keys'] += len(data)
        for key, value in data.items():
            count_type(value)
            if isinstance(value, (dict, list)):
                substats = analyze_structure(value, depth + 1)
                stats['total_keys'] += substats['total_keys']
                stats['max_depth'] = max(stats['max_depth'], substats['max_depth'])
                for dtype, count in substats['types'].items():
                    stats['types'][dtype] = stats['types'].get(dtype, 0) + count
    
    elif isinstance(data, list):
        for item in data:
            count_type(item)
            if isinstance(item, (dict, list)):
                substats = analyze_structure(item, depth + 1)
                stats['total_keys'] += substats['total_keys']
                stats['max_depth'] = max(stats['max_depth'], substats['max_depth'])
                for dtype, count in substats['types'].items():
                    stats['types'][dtype] = stats['types'].get(dtype, 0) + count
    
    return stats

def main():
    parser = argparse.ArgumentParser(
        description='Display YAML files as ASCII directory trees',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic tree display
    python yaml_tree.py config.yaml
    
    # Show values with limited depth
    python yaml_tree.py config.yaml --show-values --max-depth 3
    
    # Filter keys and truncate long values
    python yaml_tree.py config.yaml -v --filter "meta.*" --truncate 30
    
    # Include statistics
    python yaml_tree.py config.yaml --stats
        """
    )
    
    parser.add_argument('yaml_file', type=Path, help='YAML file to display')
    parser.add_argument('-v', '--show-values', action='store_true',
                       help='Show key values alongside the tree structure')
    parser.add_argument('-d', '--max-depth', type=int, default=-1,
                       help='Maximum depth to display (-1 for unlimited)')
    parser.add_argument('-f', '--filter', dest='key_filter',
                       help='Regex pattern to filter keys (case-insensitive)')
    parser.add_argument('-t', '--truncate', type=int, default=50,
                       help='Maximum length for displayed values (default: 50)')
    parser.add_argument('-s', '--stats', action='store_true',
                       help='Show structure statistics')
    parser.add_argument('--no-color', action='store_true',
                       help='Disable colored output')
    
    args = parser.parse_args()
    
    # Disable colors if requested
    if args.no_color:
        global COLORS_AVAILABLE
        COLORS_AVAILABLE = False
    
    # Load and display the YAML file
    try:
        data = load_yaml(args.yaml_file)
        
        print(f"{Style.BRIGHT}YAML Tree: {args.yaml_file}{Style.RESET_ALL}")
        print("=" * 50)
        
        tree_output = generate_tree(
            data,
            show_values=args.show_values,
            max_depth=args.max_depth,
            key_filter=args.key_filter,
            value_truncate=args.truncate
        )
        
        print(tree_output.rstrip())
        
        if args.stats:
            print_stats(data)
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
