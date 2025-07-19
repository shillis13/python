#!/usr/bin/env python3
# delete_item.py
import argparse
import sys
from yaml_utils.yaml_helpers import load_yaml, save_yaml, archive_and_update_metadata

"""
Deletes an item from a list within a YAML data structure by its index.

Args:
    data (dict): The YAML data, loaded as a Python dictionary.
    key_path (str): The dot-notation path to the list (e.g., 'rules.data').
    index (int): The index of the item to delete.

Returns:
    dict: The modified data structure.

Raises:
    KeyError: If the key_path does not resolve to a valid location.
    TypeError: If the key_path resolves to a non-list item.
    IndexError: If the index is out of bounds for the list.
"""
def delete_yaml_item(data, key_path, index):
    keys = key_path.split('.')
    current_level = data

    for k in keys:
        current_level = current_level[k]

    if not isinstance(current_level, list):
        raise TypeError(f"Error: Key '{key_path}' does not point to a list.")

    if abs(index) >= len(current_level):
        raise IndexError(f"Error: Index {index} is out of bounds for list of size {len(current_level)}.")

    del current_level[index]
    return data

def main():
    parser = argparse.ArgumentParser(description="Delete an item from a list by its index.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--key", required=True, help="The key of the list (e.g., 'rules.data').")
    parser.add_argument("--index", required=True, type=int, help="The index of the item to delete.")
    args = parser.parse_args()

    try:
        data = load_yaml(args.filepath)

        parent_key = args.key.split('.')[0]
        data = archive_and_update_metadata(data, parent_key)

        data = delete_yaml_item(data, args.key, args.index)

        save_yaml(data, args.filepath)
        print(f"✅ Successfully deleted item at index {args.index} from '{args.key}'.")

    except (KeyError, TypeError, IndexError) as e:
        print(f"Error: Could not perform deletion. Details: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()


