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


"""Validate *data_instance* against *schema_instance*.

The original project exposed a ``validate_data`` helper that returned a
boolean flag and an optional error message instead of raising
``jsonschema`` exceptions directly.  Several modules in this kata expect
that behaviour (for example :mod:`file_utils.lib_extensions`) and the
tests patch the function accordingly.  The previous implementation
wrapped :func:`jsonschema.validate` without any error handling which
caused ``SchemaError`` or ``ValidationError`` exceptions to bubble up and
abort test execution.  This broke callers that were written to handle a
``(bool, message)`` return signature.

To restore the intended API we catch the relevant exceptions and return
``(False, <message>)`` when validation fails.  A successful validation
returns ``(True, "")``.  Callers that only care about the boolean value
can ignore the message while more sophisticated code can report the
details to the user.
"""
def validate_data(data_instance, schema_instance):
    try:
        validate(instance=data_instance, schema=schema_instance)
        return True, ""
    except exceptions.ValidationError as exc:  # pragma: no cover - thin wrapper
        return False, exc.message
    except exceptions.SchemaError as exc:      # pragma: no cover - thin wrapper
        return False, exc.message


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


