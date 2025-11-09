#!/usr/bin/env python3
"""
Simple JSON Schema Draft-07 Validator (Pure Python)
Supports subset needed for MD-to-YAML conversion schemas.
No external dependencies.

Created: 2025-11-06
Project: req_1022 - MD-to-YAML Conversion System
"""

import re
from typing import Any, Dict, List, Union


class ValidationError:
    """Represents a validation error with path context"""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def __str__(self):
        return f"{self.path}: {self.message}"

    def __repr__(self):
        return f"ValidationError(path={self.path!r}, message={self.message!r})"


class SchemaValidator:
    """Validates data against JSON Schema Draft-07 subset"""

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.errors: List[ValidationError] = []

    def validate(self, data: Any, path: str = "$") -> List[ValidationError]:
        """
        Validate data against schema.

        Args:
            data: Data to validate
            path: Current path in data structure (for error reporting)

        Returns:
            List of ValidationError objects (empty if valid)
        """
        self.errors = []
        self._validate_value(data, self.schema, path)
        return self.errors

    def _validate_value(self, data: Any, schema: Dict[str, Any], path: str):
        """Validate a value against a schema"""

        # Type validation
        if "type" in schema:
            if not self._check_type(data, schema["type"]):
                self.errors.append(ValidationError(
                    path,
                    f"Expected type '{schema['type']}', got '{type(data).__name__}'"
                ))
                return  # Don't continue if type is wrong

        # Enum validation
        if "enum" in schema:
            if data not in schema["enum"]:
                self.errors.append(ValidationError(
                    path,
                    f"Value must be one of {schema['enum']}, got '{data}'"
                ))

        # String validations
        if schema.get("type") == "string":
            self._validate_string(data, schema, path)

        # Number validations
        if schema.get("type") in ["number", "integer"]:
            self._validate_number(data, schema, path)

        # Array validations
        if schema.get("type") == "array":
            self._validate_array(data, schema, path)

        # Object validations (includes patternProperties!)
        if schema.get("type") == "object":
            self._validate_object(data, schema, path)

    def _check_type(self, data: Any, type_spec: Union[str, List[str]]) -> bool:
        """Check if data matches the expected type(s)"""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }

        # Handle array of types (e.g., ["string", "null"])
        if isinstance(type_spec, list):
            return any(self._check_type(data, t) for t in type_spec)

        expected_type = type_map.get(type_spec)
        if expected_type is None:
            return True  # Unknown type, skip validation
        return isinstance(data, expected_type)

    def _validate_string(self, data: str, schema: Dict[str, Any], path: str):
        """Validate string-specific constraints"""

        # Pattern validation (regex)
        if "pattern" in schema:
            if not re.match(schema["pattern"], data):
                self.errors.append(ValidationError(
                    path,
                    f"String does not match pattern '{schema['pattern']}'"
                ))

        # Length constraints
        if "minLength" in schema and len(data) < schema["minLength"]:
            self.errors.append(ValidationError(
                path,
                f"String length {len(data)} is less than minLength {schema['minLength']}"
            ))

        if "maxLength" in schema and len(data) > schema["maxLength"]:
            self.errors.append(ValidationError(
                path,
                f"String length {len(data)} exceeds maxLength {schema['maxLength']}"
            ))

    def _validate_number(self, data: Union[int, float], schema: Dict[str, Any], path: str):
        """Validate number-specific constraints"""

        if "minimum" in schema and data < schema["minimum"]:
            self.errors.append(ValidationError(
                path,
                f"Value {data} is less than minimum {schema['minimum']}"
            ))

        if "maximum" in schema and data > schema["maximum"]:
            self.errors.append(ValidationError(
                path,
                f"Value {data} exceeds maximum {schema['maximum']}"
            ))

    def _validate_array(self, data: List, schema: Dict[str, Any], path: str):
        """Validate array-specific constraints"""

        # Length constraints
        if "minItems" in schema and len(data) < schema["minItems"]:
            self.errors.append(ValidationError(
                path,
                f"Array length {len(data)} is less than minItems {schema['minItems']}"
            ))

        if "maxItems" in schema and len(data) > schema["maxItems"]:
            self.errors.append(ValidationError(
                path,
                f"Array length {len(data)} exceeds maxItems {schema['maxItems']}"
            ))

        # Items validation (all items must match schema)
        if "items" in schema:
            for i, item in enumerate(data):
                self._validate_value(item, schema["items"], f"{path}[{i}]")

    def _validate_object(self, data: Dict, schema: Dict[str, Any], path: str):
        """
        Validate object-specific constraints.
        INCLUDES PATTERNPROPERTIES SUPPORT!
        """

        # Required fields
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    self.errors.append(ValidationError(
                        path,
                        f"Missing required field '{field}'"
                    ))

        # Property count constraints
        if "minProperties" in schema and len(data) < schema["minProperties"]:
            self.errors.append(ValidationError(
                path,
                f"Object has {len(data)} properties, minimum is {schema['minProperties']}"
            ))

        if "maxProperties" in schema and len(data) > schema["maxProperties"]:
            self.errors.append(ValidationError(
                path,
                f"Object has {len(data)} properties, maximum is {schema['maxProperties']}"
            ))

        # Validate each property
        for key, value in data.items():
            property_schema = None
            matched_pattern = False

            # 1. Check exact match in "properties"
            if "properties" in schema and key in schema["properties"]:
                property_schema = schema["properties"][key]
                matched_pattern = True

            # 2. Check pattern match in "patternProperties" (CRITICAL FOR FLEXIBLE SECTIONS!)
            if not matched_pattern and "patternProperties" in schema:
                for pattern, pattern_schema in schema["patternProperties"].items():
                    if re.match(pattern, key):
                        property_schema = pattern_schema
                        matched_pattern = True
                        break  # First matching pattern wins

            # 3. Check "additionalProperties" (only if no match found)
            if not matched_pattern and "additionalProperties" in schema:
                if schema["additionalProperties"] is False:
                    self.errors.append(ValidationError(
                        f"{path}.{key}",
                        f"Additional property '{key}' not allowed"
                    ))
                    continue
                elif isinstance(schema["additionalProperties"], dict):
                    property_schema = schema["additionalProperties"]

            # Validate the property value if we found a schema
            if property_schema:
                self._validate_value(value, property_schema, f"{path}.{key}")


def validate_yaml_against_schema(yaml_data: Dict, schema: Dict) -> List[ValidationError]:
    """
    Convenience function to validate YAML data against a schema.

    Args:
        yaml_data: Parsed YAML data as dictionary
        schema: JSON Schema as dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    validator = SchemaValidator(schema)
    return validator.validate(yaml_data)


# Self-test and example usage
if __name__ == "__main__":
    print("Simple Schema Validator - Self Test")
    print("=" * 50)

    # Test schema with patternProperties
    test_schema = {
        "type": "object",
        "required": ["metadata", "sections"],
        "properties": {
            "metadata": {
                "type": "object",
                "required": ["title", "type"],
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "enum": ["knowledge_digest", "protocol", "task_notes"]}
                }
            }
        },
        "patternProperties": {
            # Pattern for "sections" key specifically
            "^sections$": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    # Section keys must match this pattern
                    "^[a-z][a-z0-9_]*$": {
                        "type": "object",
                        "required": ["heading", "content"],
                        "properties": {
                            "heading": {"type": "string"},
                            "content": {"type": "string"}
                        }
                    }
                },
                "additionalProperties": False  # Reject keys not matching pattern
            }
        }
    }

    # Test Case 1: Valid data with flexible section names
    valid_data = {
        "metadata": {
            "title": "Test Digest",
            "type": "knowledge_digest"
        },
        "sections": {
            "why_this_architecture_exists": {
                "heading": "Why This Architecture Exists",
                "content": "Explanation..."
            },
            "architecture_overview": {
                "heading": "Architecture Overview",
                "content": "Details..."
            }
        }
    }

    print("\nTest 1: Valid data with flexible sections")
    errors = validate_yaml_against_schema(valid_data, test_schema)
    if errors:
        print("❌ FAILED - Unexpected errors:")
        for error in errors:
            print(f"  {error}")
    else:
        print("✅ PASSED - Validation successful")

    # Test Case 2: Missing required field
    invalid_data_1 = {
        "metadata": {
            "title": "Test"
            # Missing "type" field
        },
        "sections": {}
    }

    print("\nTest 2: Missing required field")
    errors = validate_yaml_against_schema(invalid_data_1, test_schema)
    if errors:
        print("✅ PASSED - Caught missing field:")
        for error in errors:
            print(f"  {error}")
    else:
        print("❌ FAILED - Should have caught missing 'type' field")

    # Test Case 3: Invalid section key pattern
    invalid_data_2 = {
        "metadata": {
            "title": "Test",
            "type": "protocol"
        },
        "sections": {
            "Why_This_Exists": {  # Uppercase - violates pattern!
                "heading": "Why",
                "content": "..."
            }
        }
    }

    print("\nTest 3: Invalid section key pattern (uppercase)")
    errors = validate_yaml_against_schema(invalid_data_2, test_schema)
    if errors:
        print("✅ PASSED - Caught pattern violation:")
        for error in errors:
            print(f"  {error}")
    else:
        print("❌ FAILED - Should have caught invalid key pattern")

    # Test Case 4: Missing section content
    invalid_data_3 = {
        "metadata": {
            "title": "Test",
            "type": "task_notes"
        },
        "sections": {
            "purpose": {
                "heading": "Purpose"
                # Missing "content" field
            }
        }
    }

    print("\nTest 4: Missing section content")
    errors = validate_yaml_against_schema(invalid_data_3, test_schema)
    if errors:
        print("✅ PASSED - Caught missing content:")
        for error in errors:
            print(f"  {error}")
    else:
        print("❌ FAILED - Should have caught missing 'content' field")

    print("\n" + "=" * 50)
    print("Self-test complete!")
