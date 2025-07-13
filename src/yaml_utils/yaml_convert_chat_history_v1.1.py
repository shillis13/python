#!/usr/bin/env python3
"""
Converts one or more Gemini chat history exports from Markdown format to
schema-compliant YAML files.

This script parses Markdown files containing chat histories, extracts the user
and assistant messages, and uses the ChatHistoryManager to create YAML files
that adhere to the v1.1 chat history schema.

Usage:
    # Single file, explicit output file name
    python convert_chat_history_to_yaml_v1.1.py chat.md -o converted.yml

    # Single file, output to a directory
    python convert_chat_history_to_yaml_v1.1.py chat.md -o ./output/

    # Multiple files, output to a directory
    python convert_chat_history_to_yaml_v1.1.py chat1.md chat2.md -o ./output/
"""

import argparse
import re
from pathlib import Path
from typing import List, Dict

try:
    from yaml_chat_manager import ChatHistoryManager
except ImportError:
    print("Error: Could not import ChatHistoryManager.")
    print("Please ensure yaml_chat_manager.py is in the same directory or in the Python path.")
    exit(1)

def parse_chat_history(markdown_content: str) -> List[Dict[str, str]]:
    """
    Parses the Markdown content of a Gemini chat history export.

    Args:
        markdown_content: The string content of the .md file.

    Returns:
        A list of dictionaries, where each dictionary represents a message
        with 'role' and 'content' keys.
    """
    pattern = r"(?s)(You asked:|Gemini Replied:)\n-*?\n(.*?)(?=\n-*\n(?:You asked:|Gemini Replied:)|$)"
    matches = re.findall(pattern, markdown_content)

    parsed_messages = []
    for role_str, content in matches:
        role = "user" if "You asked" in role_str else "assistant"
        cleaned_content = content.strip()

        if "Show thinking" in cleaned_content:
             cleaned_content = cleaned_content.split("Show thinking")[1].strip()

        message = {"role": role, "content": cleaned_content}
        parsed_messages.append(message)

    return parsed_messages


def convert_md_to_yaml(input_path: Path, output_path: Path, platform: str = "gemini", model_version: str = "1.5-pro-latest") -> bool:
    """
    Reads a Markdown chat history, converts it, and saves it as a YAML file.

    Args:
        input_path: The path to the input Markdown file.
        output_path: The path where the output YAML file will be saved.
        platform: The platform name to record in the chat history.
        model_version: The model version to record in the chat history.

    Returns:
        True if the conversion was successful, False otherwise.
    """
    result = False
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        messages = parse_chat_history(markdown_content)

        if not messages:
            print(f"Warning: No messages were parsed from '{input_path}'. Skipping.")
            return result

        chat_manager = ChatHistoryManager(platform=platform, model_version=model_version)

        for message in messages:
            chat_manager.record_message(
                role=message['role'],
                content=message['content']
            )

        # Ensure the parent directory for the output file exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        chat_manager.save(output_path)
        result = True
        print(f"✅ Successfully converted '{input_path}' to '{output_path}'")

    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_path}'")
    except Exception as e:
        print(f"An unexpected error occurred while processing '{input_path}': {e}")

    return result

def main():
    """
    Main function to handle command-line arguments and orchestrate the conversion.
    """
    parser = argparse.ArgumentParser(
        description="Convert Gemini Markdown chat histories to schema-compliant YAML files.",
        epilog="Handles single or multiple input files with flexible output path logic."
    )
    parser.add_argument(
        "input_files",
        type=Path,
        nargs='+',
        help="One or more paths to the input Markdown files."
    )
    parser.add_argument(
        "-o", "--output-path",
        type=Path,
        help="The output path. Can be a file (for single input) or a directory."
    )

    args = parser.parse_args()
    input_files = args.input_files
    output_path_arg = args.output_path

    success_count = 0
    failure_count = 0

    # --- Multiple File Logic ---
    if len(input_files) > 1:
        output_dir = output_path_arg or Path.cwd()
        if output_dir.exists() and not output_dir.is_dir():
            print(f"Error: For multiple inputs, the output path '{output_dir}' must be a directory, but it exists as a file.")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        for input_file in input_files:
            output_file_path = output_dir / (input_file.stem + ".yml")
            if convert_md_to_yaml(input_file, output_file_path):
                success_count += 1
            else:
                failure_count += 1

    # --- Single File Logic ---
    elif len(input_files) == 1:
        input_file = input_files[0]
        output_path = None
        if output_path_arg:
            # Check if the user intends for it to be a directory
            if str(output_path_arg).endswith(('/', '\\')) or (output_path_arg.exists() and output_path_arg.is_dir()):
                output_dir = Path(output_path_arg)
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / (input_file.stem + ".yml")
            else:
                # Treat it as a full file path
                output_path = output_path_arg
        else:
            # Default case: output to current directory
            output_path = Path.cwd() / (input_file.stem + ".yml")
        
        if convert_md_to_yaml(input_file, output_path):
            success_count += 1
        else:
            failure_count += 1

    print("\n--- Conversion Summary ---")
    print(f"  Total files processed: {len(input_files)}")
    print(f"  ✅ Successful: {success_count}")
    if failure_count > 0:
        print(f"  ❌ Failed or Skipped: {failure_count}")

if __name__ == "__main__":
    main()
