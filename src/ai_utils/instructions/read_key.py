# read_key.py
import argparse
import sys
import yaml

def main():
    parser = argparse.ArgumentParser(description="Read a specific key from a YAML file.")
    parser.add_argument("filepath", help="Path to the YAML file.")
    parser.add_argument("--key", required=True, help="The key to read, using dot notation (e.g., 'rules.data').")
    args = parser.parse_args()

    try:
        with open(args.filepath, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File not found at '{args.filepath}'", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}", file=sys.stderr)
        sys.exit(1)

    keys = args.key.split('.')
    value = data
    try:
        for k in keys:
            if isinstance(value, list) and k.isdigit():
                value = value[int(k)]
            else:
                value = value[k]
    except (KeyError, TypeError, IndexError):
        print(f"Error: Key '{args.key}' not found in '{args.filepath}'", file=sys.stderr)
        sys.exit(1)

    print(yaml.dump({args.key: value}, default_flow_style=False, indent=2))

if __name__ == "__main__":
    main()
