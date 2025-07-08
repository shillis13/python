#!/usr/bin/env python3
"""
Library for loading and querying file extension information from a configuration file.

This module loads and validates data from 'extensions.yml' using a schema,
and provides a command-line interface for querying type hierarchies.
"""

import argparse
import os
import sys
from pathlib import Path

# ========================================
# region Path and Package Setup
# ========================================
# To ensure 'yaml_utils' can be imported, we add the 'src' directory
# to Python's system path.
#   - Path(__file__).resolve().parent -> .../src/file_utils/
#   - .parent -> .../src/
_src_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_src_dir))
# ========================================
# endregion

# ========================================
# region Reusable YAML Library Imports
# ========================================
# This will now correctly find the yaml_utils package within the src directory.
from yaml_utils.yaml_helpers import load_yaml as load_yaml_file
from yaml_utils.yaml_validate import validate_data
from yaml_utils.yaml_treePrint import print_tree

# ========================================
# endregion

# ========================================
# region Constants and Globals
# ========================================
# Global variable to cache the loaded extension data
_extension_data = None

# Schema file is expected to be co-located with this script inside 'file_utils'.
_package_dir = Path(__file__).resolve().parent
# SCHEMA_FILE = _package_dir / "extensions.schema.yml"
# ========================================
# endregion

# ========================================
# region Data Loading and Parsing
# ========================================

# In lib_extensions.py

# ========================================
# region Helper Functions
# ========================================

"""
Searches for a file in a list of directories.

Args:
    filename (str): The name of the file to find.
    search_dirs (list[Path]): A list of pathlib.Path objects representing the
        directories to search in.

Returns:
    Path | None: The path to the first instance of the file found, or None.
"""
def find_file(filename: str, search_dirs: list[Path]) -> Path | None:
    found_path = None
    for directory in search_dirs:
        file_path = directory / filename
        if file_path.is_file():
            found_path = file_path
            break
    result = found_path
    return result

# ========================================
# endregion

"""
Recursively parse validated data to build the internal query maps.

Args:
    data (dict): The dictionary of type data to parse.
    parent (str | None): The name of the parent type for the current recursion level.
    type_map (dict): The dictionary of type information to populate.
    ext_map (dict): The dictionary of extension-to-type mappings to populate.
"""
def _parse_hierarchy_recursive(data: dict, parent: str | None, type_map: dict, ext_map: dict):
    for type_name, type_data in data.items():
        if not isinstance(type_data, dict):
            continue

        type_map[type_name] = {
            'parent': parent,
            'children': list(type_data.get('sub_types', {}).keys()),
            'extensions': type_data.get('extensions', [])
        }

        for ext in type_data.get('extensions', []):
            ext_map[ext] = type_name

        if 'sub_types' in type_data:
            _parse_hierarchy_recursive(type_data['sub_types'], type_name, type_map, ext_map)

# ---

"""
Loads, validates, and parses the extension data from the config file.

This function finds the extensions.yml file, validates it against a schema,
and then parses it into an internal format for querying. The result is cached
globally.

Returns:
    dict | None: The fully parsed data dictionary, or None if an error occurs.
"""
def get_extension_data() -> dict | None:
    global _extension_data
    if _extension_data is not None:
        return _extension_data

    search_dirs = [Path(os.getcwd()), _package_dir.parent.parent / 'data']
    config_path = find_file("extensions.yml", search_dirs)

    if not config_path:
        # ... (error handling is unchanged)
        return None

    # Dynamically find the schema file in the same search paths.
    schema_path = find_file("extensions.schema.yml", search_dirs)
    if not schema_path:
        print("Error: Could not find 'extensions.schema.yml'.")
        print(f"Searched in: {[str(d) for d in search_dirs]}")
        return None

    print(f"Loading data from: {config_path}")
    print(f"Loading schema from: {schema_path}")
    schema = load_yaml_file(schema_path)
    data = load_yaml_file(config_path)

    if not schema or not data:
        return None

    is_valid, message = validate_data(data, schema)
    if not is_valid:
        print(f"Error: 'extensions.yml' is not valid.\n{message}")
        return None

    type_map = {}
    ext_map = {}
    if 'file_types' in data:
        _parse_hierarchy_recursive(data['file_types'], None, type_map, ext_map)
        _extension_data = {'types': type_map, 'extensions': ext_map, 'source': data}

    result = _extension_data
    return result

# ========================================
# endregion

# ========================================
# region Data Manipulation
# ========================================

"""
Recursively creates a deep copy of the data with all 'extensions' keys removed.

Args:
    data (dict): The data dictionary to prune.

Returns:
    dict: A new dictionary with the 'extensions' keys removed.
"""
def _prune_extensions_recursive(data: dict) -> dict:
    pruned_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            pruned_value = _prune_extensions_recursive(value)
            if 'extensions' in pruned_value:
                del pruned_value['extensions']
            pruned_data[key] = pruned_value
        elif key != 'extensions':
            pruned_data[key] = value

    if 'sub_types' in pruned_data and isinstance(pruned_data['sub_types'], dict):
         pruned_data['sub_types'] = _prune_extensions_recursive(pruned_data['sub_types'])

    result = pruned_data
    return result

# ========================================
# endregion

# ========================================
# region CLI Printing Functions
# ========================================

"""
Prints the entire type hierarchy using the tree printer utility.

Args:
    data (dict): The main data dictionary returned by get_extension_data().
    show_extensions (bool): If True, the tree will include extension nodes.
        If False, they are pruned before printing.
"""
def print_full_hierarchy(data: dict, show_extensions: bool):
    if not data or 'source' not in data:
        print("No source data to display.")
        return

    data_to_print = data['source']['file_types']
    if not show_extensions:
        data_to_print = _prune_extensions_recursive(data_to_print)

    print("File Type Hierarchy:")
    print_tree(data_to_print)

# ---

"""
Prints the type of a given extension and optionally its ancestors.

Args:
    ext (str): The file extension to look up (e.g., '.txt').
    data (dict): The main data dictionary.
    show_ancestors (bool): If True, prints the hierarchy of parent types.
"""
def print_type_from_extension(ext: str, data: dict, show_ancestors: bool):
    type_name = data['extensions'].get(ext)
    if not type_name:
        print(f"Extension '{ext}' not found.")
        return

    print(f"Extension: {ext}\nType: {type_name}")
    if show_ancestors:
        print("Ancestors:")
        current_type = type_name
        while data['types'][current_type]['parent']:
            parent = data['types'][current_type]['parent']
            print(f"  └── {parent}")
            current_type = parent

# ---

"""
Handles queries for a given type, such as finding ancestors or descendants.

Args:
    type_name (str): The type name to query.
    data (dict): The main data dictionary.
    ancestors (bool): If True, prints all parent types.
    descendants_tree (bool): If True, prints a tree of all child types.
    descendants_flat (bool): If True, prints a flat list of all descendant extensions.
"""
def print_type_query(type_name: str, data: dict, ancestors: bool, descendants_tree: bool, descendants_flat: bool):
    if type_name not in data['types']:
        print(f"Type '{type_name}' not found.")
        return

    if ancestors:
        print(f"Ancestors of '{type_name}':")
        current_type = type_name
        parent = data['types'][current_type]['parent']
        if not parent:
            print("  (No parents, this is a root type)")
        while parent:
            print(f"  └── {parent}")
            current_type = parent
            parent = data['types'][current_type]['parent']

    if descendants_tree:
        print(f"Descendant tree for '{type_name}':")
        q = [(data['source']['file_types'], type_name)]
        sub_tree = None
        while q:
            current_data, target = q.pop(0)
            if target in current_data:
                sub_tree = {target: current_data[target]}
                break
            for key, value in current_data.items():
                if isinstance(value, dict) and 'sub_types' in value:
                    q.append((value['sub_types'], target))

        if sub_tree:
            print_tree(sub_tree)
        else:
            print(f"Could not find '{type_name}' in source data to print tree.")

    if descendants_flat:
        print(f"All descendant extensions for '{type_name}':")
        all_exts = []
        q = [type_name]
        while q:
            current = q.pop(0)
            all_exts.extend(data['types'][current]['extensions'])
            q.extend(data['types'][current]['children'])
        for ext in sorted(list(set(all_exts))):
            print(f"  - {ext}")

# ========================================
# endregion

# ========================================
# region Main Entry
# ========================================

"""
Main entry point for parsing command-line arguments and executing the requested command.

Returns:
    int: An exit code, 0 for success and 1 for failure.
"""
def main():
    parser = argparse.ArgumentParser(description="Query file extension and type hierarchies.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'tree' command
    parser_tree = subparsers.add_parser('tree', help='Display the full hierarchy of types.')
    parser_tree.add_argument(
        '-e', '--show-extensions',
        action='store_true',
        help='Include extensions in the tree view.'
    )

    # 'get-type' command
    parser_get_type = subparsers.add_parser('get-type', help='Find the type for a given extension.')
    parser_get_type.add_argument('extension', type=str, help='The file extension to look up (e.g., .txt).')
    parser_get_type.add_argument(
        '-a', '--ancestors',
        action='store_true',
        help='Show the full ancestor path for the type.'
    )

    # 'query-type' command
    parser_query_type = subparsers.add_parser('query-type', help='Query information about a specific type.')
    parser_query_type.add_argument('type_name', type=str, help='The type name to query.')
    group = parser_query_type.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-a', '--ancestors',
        action='store_true',
        help='List all parent types up to the root.'
    )
    group.add_argument(
        '-t', '--descendants-tree',
        action='store_true',
        help='Display all descendants in a tree format.'
    )
    group.add_argument(
        '-f', '--descendants-flat',
        action='store_true',
        help='Provide a flat list of all descendant extensions.'
    )

    args = parser.parse_args()
    data = get_extension_data()

    if not data:
        result = 1
        return result

    if args.command == 'tree':
        print_full_hierarchy(data, args.show_extensions)
    elif args.command == 'get-type':
        print_type_from_extension(args.extension, data, args.ancestors)
    elif args.command == 'query-type':
        print_type_query(args.type_name, data, args.ancestors, args.descendants_tree, args.descendants_flat)
    else:
        parser.print_help()

    result = 0
    return result

if __name__ == "__main__":
    main()
# ========================================
# endregion

