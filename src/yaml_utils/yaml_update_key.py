#!/usr/bin/env python3
# update_key.py
import argparse
import sys
from yaml_utils.yaml_helpers import load_yaml, save_yaml, archive_and_update_metadata

"""
Updates a value for a specific key in a YAML data structure.

Navigates to the key using dot notation and sets the new value. It can
also perform basic type inference for booleans and integers based on the
original value's type.

Args:
    data (dict): The YAML data, loaded as a Python dictionary.
    key_path (str): The dot-notation path to the key to update (e.g., 'persona.data').
    new_value (str): The new value to set for the key (will be type-inferred).

Returns:
    dict: The modified data structure.

Raises:
    KeyError: If the key_path (except for the final key) cannot be resolved.
"""


def update_yaml_key(data, key_path, new_value):
    keys = key_path.split(".")
    current_level = data

    for k in keys[:-1]:
        current_level = current_level[k]

    final_key = keys[-1]

    # Check type of existing value to handle int/bool correctly
    inferred_value = new_value
    try:
        original_value = current_level[final_key]
        if isinstance(original_value, bool):
            inferred_value = str(new_value).lower() in ["true", "1", "t", "y", "yes"]
        elif isinstance(original_value, int):
            inferred_value = int(new_value)
    except (KeyError, TypeError):
        pass  # Key doesn't exist yet, so no type to check against

    current_level[final_key] = inferred_value
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Update a value for a specific key, archiving the previous state."
    )
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument(
        "--key",
        required=True,
        help="The key to update, using dot notation (e.g., 'persona.data').",
    )
    parser.add_argument(
        "--value", required=True, help="The new value to set for the key."
    )
    args = parser.parse_args()

    try:
        data = load_yaml(args.filepath)

        parent_key = args.key.split(".")[0]
        data = archive_and_update_metadata(data, parent_key)

        data = update_yaml_key(data, args.key, args.value)

        save_yaml(data, args.filepath)
        print(
            f"✅ Successfully updated key '{args.key}' in '{args.filepath}'. Previous state archived."
        )

    except (KeyError, TypeError):
        print(
            f"Error: Key '{args.key}' could not be resolved for update.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
