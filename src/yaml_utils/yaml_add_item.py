# add_item.py
import argparse
import sys
from helpers import load_yaml, save_yaml, archive_and_update_metadata

def main():
    parser = argparse.ArgumentParser(description="Add an item to a list within the YAML, archiving the parent state.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--key", required=True, help="The key of the list to add to (e.g., 'rules.data').")
    parser.add_argument("--value", required=True, help="The new value to append to the list.")
    args = parser.parse_args()

    data = load_yaml(args.filepath)
    
    parent_key = args.key.split('.')[0]
    data = archive_and_update_metadata(data, parent_key)

    keys = args.key.split('.')
    current_level = data
    try:
        for k in keys:
            current_level = current_level[k]
        
        if not isinstance(current_level, list):
            print(f"Error: Key '{args.key}' does not point to a list.", file=sys.stderr)
            sys.exit(1)
        
        current_level.append(args.value)

    except (KeyError, TypeError):
        print(f"Error: Key '{args.key}' could not be resolved.", file=sys.stderr)
        sys.exit(1)

    save_yaml(data, args.filepath)
    print(f"✅ Successfully added item to '{args.key}' in '{args.filepath}'.")

if __name__ == "__main__":
    main()
