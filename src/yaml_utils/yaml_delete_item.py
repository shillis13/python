# delete_item.py
import argparse
import sys
from helpers import load_yaml, save_yaml, archive_and_update_metadata

def main():
    parser = argparse.ArgumentParser(description="Delete an item from a list by its index.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--key", required=True, help="The key of the list (e.g., 'rules.data').")
    parser.add_argument("--index", required=True, type=int, help="The index of the item to delete.")
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
        
        if abs(args.index) >= len(current_level):
            print(f"Error: Index {args.index} is out of bounds for list of size {len(current_level)}.", file=sys.stderr)
            sys.exit(1)

        del current_level[args.index]

    except (KeyError, TypeError):
        print(f"Error: Key '{args.key}' could not be resolved.", file=sys.stderr)
        sys.exit(1)

    save_yaml(data, args.filepath)
    print(f"✅ Successfully deleted item at index {args.index} from '{args.key}'.")

if __name__ == "__main__":
    main()
