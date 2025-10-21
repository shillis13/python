#!/usr/bin/env python3
"""
Chat Index Manager

A Python class and CLI tool to create, update, and search the master
chat_index.yml file, which catalogs all individual chat history files.
"""

import yaml
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


# Assume yaml_helpers.py is in the same directory or accessible in the path
# For self-containment, we'll include the necessary helper functions.
# Load a YAML file and handle errors.
def load_yaml(filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Loads a YAML file and handles errors."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None  # Return None to signify we need to create it
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None


# Save data to a YAML file.
def save_yaml(data: Dict[str, Any], filepath: Union[str, Path]) -> None:
    """Saves data to a YAML file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)
    except IOError as e:
        print(f"Error writing to file '{filepath}': {e}")


# Manage the lifecycle of the master chat index.
class ChatIndexManager:
    """Manages the lifecycle of the master chat index."""

    def __init__(self, index_filepath: Union[str, Path]):
        """
        Initializes the ChatIndexManager.

        Args:
            index_filepath: Path to the master chat_index.yml file.
        """
        self.filepath = Path(index_filepath)
        self.index_data = load_yaml(self.filepath)
        if not self.index_data:
            print(
                f"Index file not found or empty. Initializing new index at {self.filepath}"
            )
            self.index_data = self._initialize_new_index()

    def _initialize_new_index(self) -> Dict[str, Any]:
        """Creates the structure for a new, empty chat index."""
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "metadata": {
                "last_updated": now_iso,
                "version": 1,
                "total_conversations": 0,
                "format_version": "1.1",
            },
            "conversations": [],
        }

    def _add_or_update_entry(self, new_entry: Dict[str, Any]):
        """
        Core logic to add or update a single entry in the index.

        Args:
            new_entry: A dictionary containing the fully-formed index entry.
        """
        conv_id = new_entry.get("conversation_id")
        if not conv_id:
            print("Error: Entry to be added is missing a 'conversation_id'.")
            return

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        existing_entry = next(
            (
                item
                for item in self.index_data["conversations"]
                if item["conversation_id"] == conv_id
            ),
            None,
        )

        if existing_entry:
            print(f"Updating existing index entry for conversation: {conv_id}")
            # Update all fields from the new entry, but manage version and update time
            existing_entry.update(new_entry)
            existing_entry["last_updated"] = now_iso
            existing_entry["version"] = existing_entry.get("version", 1) + 1
        else:
            print(f"Adding new index entry for conversation: {conv_id}")
            # Ensure required fields are present for a new entry
            new_entry["last_updated"] = now_iso
            if "version" not in new_entry:
                new_entry["version"] = 1
            self.index_data["conversations"].append(new_entry)
            self.index_data["metadata"]["total_conversations"] += 1

        # Update index metadata and save
        self.index_data["metadata"]["last_updated"] = now_iso
        self.index_data["metadata"]["version"] += 1
        self.save()

    def add_from_cli(
        self,
        history_filepath: Union[str, Path],
        title: str,
        abstract: str,
        key_insights: List[str],
        tags: List[str],
    ):
        """
        Builds an entry from CLI arguments and adds it to the index.
        This is a convenience wrapper around _add_or_update_entry.
        """
        history_data = load_yaml(history_filepath)
        if not history_data:
            print(f"Error: Could not load history file {history_filepath}")
            return

        history_meta = history_data.get("metadata", {})
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        entry_to_add = {
            "conversation_id": history_meta.get("conversation_id"),
            "title": title,
            "abstract": abstract,
            "key_insights": key_insights,
            "start_date": history_meta.get("created", now_iso),
            "tags": sorted(list(set(tags))),
            "file_path": str(history_filepath),
            "message_count": history_meta.get("total_messages", 0),
        }
        self._add_or_update_entry(entry_to_add)

    def add_from_file(self, entry_filepath: Union[str, Path]):
        """
        Adds a pre-formatted entry from a YAML file to the index.
        This is a convenience wrapper around _add_or_update_entry.
        """
        entry_data = load_yaml(entry_filepath)
        if not entry_data:
            print(f"Error: Could not load entry file {entry_filepath}")
            return

        # If the file contains a list of entries, process the first one.
        if isinstance(entry_data, list):
            if not entry_data:
                print(f"Error: Entry file {entry_filepath} is an empty list.")
                return
            entry_to_add = entry_data[0]
        else:
            entry_to_add = entry_data

        self._add_or_update_entry(entry_to_add)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches the index for conversations matching a query.
        """
        query = query.lower()
        results = []
        for entry in self.index_data.get("conversations", []):
            if (
                query in entry.get("title", "").lower()
                or query in entry.get("abstract", "").lower()
                or any(
                    query in insight.lower()
                    for insight in entry.get("key_insights", [])
                )
                or any(query in tag.lower() for tag in entry.get("tags", []))
            ):
                if entry not in results:
                    results.append(entry)
        return results

    def save(self):
        """Saves the index data back to its file."""
        save_yaml(self.index_data, self.filepath)
        print(f"✅ Chat index saved to {self.filepath}")


# Command-line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the master chat index.")
    parser.add_argument("index_file", help="Path to the master chat_index.yml file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'add-from-cli' command
    add_cli_parser = subparsers.add_parser(
        "add-from-cli", help="Build and add an entry from command-line arguments."
    )
    add_cli_parser.add_argument(
        "history_file", help="Path to the chat_history.yml file to index."
    )
    add_cli_parser.add_argument(
        "--title", required=True, help="A descriptive title for the conversation."
    )
    add_cli_parser.add_argument(
        "--abstract", required=True, help="A paragraph summary of the conversation."
    )
    add_cli_parser.add_argument(
        "--insights",
        nargs="+",
        default=[],
        help="A list of key insights or take-aways.",
    )
    add_cli_parser.add_argument(
        "--tags", nargs="+", default=[], help="A list of tags for searching."
    )

    # 'add-from-file' command
    add_file_parser = subparsers.add_parser(
        "add-from-file", help="Add a pre-formatted YAML entry from a file."
    )
    add_file_parser.add_argument(
        "entry_file", help="Path to the YAML file containing the single entry to add."
    )

    # 'search' command
    search_parser = subparsers.add_parser(
        "search", help="Search the index for conversations."
    )
    search_parser.add_argument("query", help="The term to search for.")

    args = parser.parse_args()
    manager = ChatIndexManager(args.index_file)

    if args.command == "add-from-cli":
        manager.add_from_cli(
            history_filepath=args.history_file,
            title=args.title,
            abstract=args.abstract,
            key_insights=args.insights,
            tags=args.tags,
        )
    elif args.command == "add-from-file":
        manager.add_from_file(args.entry_file)
    elif args.command == "search":
        search_results = manager.search(args.query)
        if search_results:
            print(f"\nFound {len(search_results)} match(es) for '{args.query}':")
            # ... (printing logic remains the same)
        else:
            print(f"No results found for '{args.query}'.")
