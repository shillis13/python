#!/usr/bin/env python3
# yaml_validate.py

"""
Validates a YAML data file against a YAML schema file.

This script can be run from the command line or imported as a module.
When imported, it provides the `validate_data` function.
"""

import argparse
import sys
import yaml
from jsonschema import validate, exceptions

"""
Validates a Python data object against a schema object.

Args:
    data_instance (dict or list): The Python object loaded from a YAML/JSON file.
    schema_instance (dict): The Python object representing the validation schema.

Returns:
    tuple[bool, str]: A tuple where the first element indicates whether
        validation succeeded and the second contains an error message when
        validation fails.
"""
def validate_data(data_instance, schema_instance):
    try:
        validate(instance=data_instance, schema=schema_instance)
    except exceptions.ValidationError as e:
        path = " -> ".join(map(str, e.path))
        message = e.message
        if path:
            message += f"\nPath: {path}"
        return False, message
    except exceptions.SchemaError as e:
        return False, f"Schema error: {e.message}"

    return True, ""


"""
Main function for command-line execution.
Parses arguments, loads files, and calls the validation logic.
"""
def main():
    parser = argparse.ArgumentParser(description="Validate a YAML file against a schema.")
    parser.add_argument("data_file", help="Path to the YAML data file to validate.")
    parser.add_argument("schema_file", help="Path to the YAML schema file.")
    args = parser.parse_args()

    try:
        with open(args.data_file, 'r', encoding='utf-8') as f:
            data_instance = yaml.safe_load(f)

        with open(args.schema_file, 'r', encoding='utf-8') as f:
            schema_instance = yaml.safe_load(f)

    except FileNotFoundError as e:
        print(f"Error: File not found - {e.filename}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Could not parse YAML file - {e}", file=sys.stderr)
        sys.exit(1)

    is_valid, message = validate_data(data_instance=data_instance, schema_instance=schema_instance)
    if is_valid:
        print(f"✅ Validation successful: '{args.data_file}' adheres to the schema in '{args.schema_file}'.")
    else:
        print(f"❌ VALIDATION FAILED for '{args.data_file}':", file=sys.stderr)
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


