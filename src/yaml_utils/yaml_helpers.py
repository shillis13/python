# helpers.py
from datetime import datetime, timezone
import sys
import yaml


def get_utc_timestamp():
    """Returns the current time in UTC ISO 8601 format with a Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_yaml(filepath):
    """Loads a YAML file and handles errors."""
    try:
        with open(filepath, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}", file=sys.stderr)
        sys.exit(1)


def save_yaml(data, filepath):
    """Saves data to a YAML file."""
    try:
        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)
    except IOError as e:
        print(f"Error writing to file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def archive_and_update_metadata(data, parent_key_str):
    """
    Archives a section of the data and updates its metadata.
    Returns the modified data object.
    """
    if "." in parent_key_str:
        print("Error: Archiving only supported for top-level keys.", file=sys.stderr)
        sys.exit(1)

    parent_key = parent_key_str
    if parent_key not in data:
        print(
            f"Error: Parent key '{parent_key}' not found for archiving.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Create the archive key
    timestamp = get_utc_timestamp()
    archive_key = f"{parent_key}_{timestamp}"

    # Deep copy the current data to the archive key
    # A simple dict copy is sufficient here as we're archiving the whole block
    data[archive_key] = data[parent_key].copy()

    # Update metadata on the original key
    if "metadata" in data[parent_key]:
        data[parent_key]["metadata"]["version"] = (
            data[parent_key]["metadata"].get("version", 0) + 1
        )
        data[parent_key]["metadata"]["last_updated"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    return data
