#!/usr/bin/env python3
# add_item.py
import argparse
import sys
from yaml_utils.yaml_helpers import load_yaml, save_yaml, archive_and_update_metadata

"""
Adds an item to a list within a YAML data structure.

Args:
    data (dict): The YAML data, loaded as a Python dictionary.
    key_path (str): The dot-notation path to the list (e.g., 'rules.data').
    value (any): The new value to append to the list.

Returns:
    dict: The modified data structure.

Raises:
    KeyError: If the key_path does not resolve to a valid location.
    TypeError: If the key_path resolves to a non-list item.
"""


def add_yaml_item(data, key_path, value):
    keys = key_path.split(".")
    current_level = data

    for k in keys:
        current_level = current_level[k]

    if not isinstance(current_level, list):
        raise TypeError(f"Error: Key '{key_path}' does not point to a list.")

    current_level.append(value)
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Add an item to a list within the YAML, archiving the parent state."
    )
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument(
        "--key",
        required=True,
        help="The key of the list to add to (e.g., 'rules.data').",
    )
    parser.add_argument(
        "--value", required=True, help="The new value to append to the list."
    )
    args = parser.parse_args()

    try:
        data = load_yaml(args.filepath)

        parent_key = args.key.split(".")[0]
        data = archive_and_update_metadata(data, parent_key)

        data = add_yaml_item(data, args.key, args.value)

        save_yaml(data, args.filepath)
        print(f"✅ Successfully added item to '{args.key}' in '{args.filepath}'.")

    except (KeyError, TypeError) as e:
        print(
            f"Error: Could not resolve key '{args.key}'. Details: {e}", file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
