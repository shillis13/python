# merge.py
import argparse
import sys
from helpers import load_yaml, save_yaml

def main():
    parser = argparse.ArgumentParser(description="Merge two instruction files.")
    parser.add_argument("base_file", help="The base YAML file (the version to merge INTO).")
    parser.add_argument("changes_file", help="The YAML file with changes to merge FROM.")
    parser.add_argument("output_file", help="The path to save the merged YAML file.")
    args = parser.parse_args()

    base_data = load_yaml(args.base_file)
    changes_data = load_yaml(args.changes_file)
    
    merged_data = base_data.copy()
    conflicts = []

    for key, value in changes_data.items():
        if key not in merged_data:
            # Key exists only in changes_file, so add it
            merged_data[key] = value
            print(f"MERGE INFO: Added new key '{key}' from '{args.changes_file}'.")
        elif merged_data[key] != value:
            # Key exists in both but values are different -> CONFLICT
            # For this simple script, we'll flag it. A more complex script
            # would ask for user input.
            conflicts.append(key)
    
    if conflicts:
        print("❌ MERGE FAILED: The following top-level keys have conflicts:", file=sys.stderr)
        for key in conflicts:
            print(f"  - {key}", file=sys.stderr)
        print("Please resolve conflicts manually.", file=sys.stderr)
        sys.exit(1)

    save_yaml(merged_data, args.output_file)
    print(f"✅ Merge successful (no conflicts found). Output saved to '{args.output_file}'.")

if __name__ == "__main__":
    main()
