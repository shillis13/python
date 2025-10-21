#!/usr/bin/env python3
# ========================================
# region load_chat_history_file
"""
Load and validate a chat history YAML file.

Reads YAML file, validates against schema, and returns parsed content.
Handles file errors gracefully with logging.

Args:
    file_path (str): Path to YAML chat history file

Returns:
    dict: Parsed chat history data, or None if error
"""


# ========================================
# endregion
def load_chat_history_file(file_path):
    import yaml
    from pathlib import Path

    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        print(f"❌ File not found: {file_path}")
        return None

    try:
        with open(file_path_obj, "r", encoding="utf-8") as file:
            content = yaml.safe_load(file)

        # Basic validation
        validation_result = validate_chat_history_structure(content)
        if not validation_result:
            print(f"❌ Invalid chat history structure: {file_path}")
            return None

        print(f"✅ Loaded: {file_path}")
        return content

    except yaml.YAMLError as e:
        print(f"❌ YAML error in {file_path}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None
