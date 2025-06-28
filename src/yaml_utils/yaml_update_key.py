# update_key.py
import argparse
import sys
from helpers import load_yaml, save_yaml, archive_and_update_metadata

def main():
    parser = argparse.ArgumentParser(description="Update a value for a specific key, archiving the previous state.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--key", required=True, help="The key to update, using dot notation (e.g., 'persona.data').")
    parser.add_argument("--value", required=True, help="The new value to set for the key.")
    args = parser.parse_args()

    data = load_yaml(args.filepath)
    
    # Archive the top-level parent before making changes
    parent_key = args.key.split('.')[0]
    data = archive_and_update_metadata(data, parent_key)

    # Navigate to the key and update it
    keys = args.key.split('.')
    current_level = data
    try:
        for i, k in enumerate(keys[:-1]):
            current_level = current_level[k]
        
        # Check type of value to handle int/bool correctly
        new_value = args.value
        try:
            if isinstance(current_level[keys[-1]], bool):
                new_value = new_value.lower() in ['true', '1', 't', 'y', 'yes']
            elif isinstance(current_level[keys[-1]], int):
                new_value = int(new_value)
        except (KeyError, TypeError):
             pass # Key doesn't exist yet, so no type to check against

        current_level[keys[-1]] = new_value
    except (KeyError, TypeError):
        print(f"Error: Key '{args.key}' could not be resolved for update.", file=sys.stderr)
        sys.exit(1)

    save_yaml(data, args.filepath)
    print(f"✅ Successfully updated key '{args.key}' in '{args.filepath}'. Previous state archived.")

if __name__ == "__main__":
    main()
