# prune.py
import argparse
import sys
import re
from helpers import load_yaml, save_yaml

def main():
    parser = argparse.ArgumentParser(description="Prune the history of archived keys in an instruction file.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--keep", type=int, default=5, help="The number of most recent archives to keep for each key.")
    args = parser.parse_args()

    data = load_yaml(args.filepath)
    
    keys_to_prune = {}
    # Regex to find archived keys like 'rules_20250626T212838Z'
    archive_pattern = re.compile(r"^([a-zA-Z0-9]+)_(\d{8}T\d{6}Z)$")

    for key in data.keys():
        match = archive_pattern.match(key)
        if match:
            base_key, timestamp = match.groups()
            if base_key not in keys_to_prune:
                keys_to_prune[base_key] = []
            keys_to_prune[base_key].append(key)

    if not keys_to_prune:
        print("No archived keys found to prune.")
        sys.exit(0)

    pruned_count = 0
    for base_key, archives in keys_to_prune.items():
        # Sort archives chronologically (newest first)
        archives.sort(reverse=True)
        
        if len(archives) > args.keep:
            keys_to_delete = archives[args.keep:]
            for key_to_delete in keys_to_delete:
                del data[key_to_delete]
                pruned_count += 1
            print(f"Pruned {len(keys_to_delete)} old archives for base key '{base_key}'.")

    if pruned_count > 0:
        save_yaml(data, args.filepath)
        print(f"✅ Pruning complete. Total archives removed: {pruned_count}.")
    else:
        print("No archives needed pruning based on the '--keep' value.")

if __name__ == "__main__":
    main()
