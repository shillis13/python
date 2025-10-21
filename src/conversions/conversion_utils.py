# conversion_utils.py
import json
import yaml
import os


"""
* Reads the entire content of a specified file.
* 
* rgs:
*    file_path (str): The full path to the file.
* 
* eturns:
*    str: The content of the file as a string.
*    dict: A dictionary with an 'error' key if reading fails.
"""


def read_file_content(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return {"error": f"Failed to read file {file_path}: {e}"}


"""
* Writes a string of content to a specified file, overwriting it.
* 
* Args:
*    file_path (str): The full path to the output file.
*    content (str): The string content to write.
*
*Returns:
*    dict: A dictionary with 'success': True or an 'error' key.
"""


def write_file_content(file_path, content):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": f"Failed to write to file {file_path}: {e}"}


"""
* Parses a JSON formatted string into a Python object.
*
* Args:
*    content (str): The JSON string to parse.
*
* Returns:
*    dict: The parsed Python dictionary.
*    dict: A dictionary with an 'error' key if parsing fails.
"""


def load_json_from_string(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decoding failed: {e}"}


"""
* Converts a Python dictionary to a nicely formatted JSON string.
*
* Args:
*     data (dict): The dictionary to convert.
* 
* Returns:
*     str: The formatted JSON string.
"""


def to_json_string(data):
    return json.dumps(data, indent=2)


"""
* Parses a YAML formatted string into a Python object.
* 
* Args:
*     content (str): The YAML string to parse.
* 
* Returns:
*     dict: The parsed Python dictionary.
*     dict: A dictionary with an 'error' key if parsing fails.
"""


def load_yaml_from_string(content):
    try:
        # Use safe_load_all to handle multi-document streams.
        # It returns a generator, so we convert it to a list.
        docs = list(yaml.safe_load_all(content))
        # If there was only one document, return it directly for simplicity.
        # Otherwise, return the list of documents.
        return docs[0] if len(docs) == 1 else docs
    except yaml.YAMLError as e:
        return {"error": f"YAML parsing failed: {e}"}


"""
* Converts a Python dictionary to a YAML formatted string.
* 
* Args:
*     data (dict): The dictionary to convert.
* 
*  Returns:
*    str: The YAML string.
"""


def to_yaml_string(data):
    return yaml.dump(data, sort_keys=False)
