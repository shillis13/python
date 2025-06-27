# validate.py
import argparse
import sys
import yaml
from jsonschema import validate, exceptions

def main():
    parser = argparse.ArgumentParser(description="Validate an instruction file against the official schema.")
    parser.add_argument("instruction_file", help="Path to the instruction YAML file to validate.")
    parser.add_argument("--schema-file", default="instructions_schema.yaml", help="Path to the schema file.")
    args = parser.parse_args()

    try:
        with open(args.instruction_file, 'r') as f:
            instruction_data = yaml.safe_load(f)
        
        with open(args.schema_file, 'r') as f:
            schema_data = yaml.safe_load(f)
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e.filename}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Could not parse YAML file - {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate(instance=instruction_data, schema=schema_data)
        print(f"✅ Validation successful: '{args.instruction_file}' adheres to the schema.")
    except exceptions.ValidationError as e:
        print(f"❌ VALIDATION FAILED for '{args.instruction_file}':", file=sys.stderr)
        print(f"Error: {e.message}", file=sys.stderr)
        print(f"Path: {' -> '.join(map(str, e.path))}", file=sys.stderr)
        sys.exit(1)
    except exceptions.SchemaError as e:
        print(f"❌ SCHEMA ERROR:", file=sys.stderr)
        print(f"The schema file '{args.schema_file}' is invalid.", file=sys.stderr)
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
