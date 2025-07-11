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
def load_yaml(filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Loads a YAML file and handles errors."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None # Return None to signify we need to create it
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None

def save_yaml(data: Dict[str, Any], filepath: Union[str, Path]) -> None:
    """Saves data to a YAML file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)
    except IOError as e:
        print(f"Error writing to file '{filepath}': {e}")


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
            print(f"Index file not found or empty. Initializing new index at {self.filepath}")
            self.index_data = self._initialize_new_index()

    def _initialize_new_index(self) -> Dict[str, Any]:
        """Creates the structure for a new, empty chat index."""
        now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return {
            "metadata": {
                "last_updated": now_iso,
                "version": 1,
                "total_conversations": 0,
                "format_version": "1.1"
            },
            "conversations": []
        }

    def add_or_update_from_history(self, history_filepath: Union[str, Path], title: str, abstract: str, key_insights: List[str], tags: List[str]):
        """
        Adds a new conversation to the index or updates an existing one.

        Args:
            history_filepath: Path to the chat_history.yml file to be indexed.
            title: A human-readable title for the conversation.
            abstract: A paragraph-length summary of the conversation.
            key_insights: A list of key take-aways from the conversation.
            tags: A list of tags for searching.
        """
        history_data = load_yaml(history_filepath)
        if not history_data:
            print(f"Error: Could not load history file {history_filepath}")
            return

        history_meta = history_data.get("metadata", {})
        conv_id = history_meta.get("conversation_id")
        if not conv_id:
            print(f"Error: No conversation_id found in {history_filepath}")
            return

        now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Check if this conversation already exists in the index
        existing_entry = next((item for item in self.index_data["conversations"] if item["conversation_id"] == conv_id), None)

        if existing_entry:
            # Update the existing entry
            print(f"Updating existing index entry for conversation: {conv_id}")
            existing_entry["title"] = title
            existing_entry["abstract"] = abstract
            existing_entry["key_insights"] = key_insights
            existing_entry["tags"] = sorted(list(set(tags))) # Deduplicate and sort
            existing_entry["last_updated"] = now_iso
            existing_entry["version"] = existing_entry.get("version", 1) + 1
            existing_entry["message_count"] = history_meta.get("total_messages", 0)
        else:
            # Add a new entry
            print(f"Adding new index entry for conversation: {conv_id}")
            new_entry = {
                "conversation_id": conv_id,
                "title": title,
                "abstract": abstract,
                "key_insights": key_insights,
                "start_date": history_meta.get("created", now_iso),
                "last_updated": now_iso,
                "version": 1,
                "tags": sorted(list(set(tags))),
                "file_path": str(history_filepath),
                "message_count": history_meta.get("total_messages", 0)
            }
            self.index_data["conversations"].append(new_entry)
            self.index_data["metadata"]["total_conversations"] += 1
        
        # Update index metadata
        self.index_data["metadata"]["last_updated"] = now_iso
        self.index_data["metadata"]["version"] += 1
        
        self.save()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches the index for conversations matching a query.

        Args:
            query: The search term. Searches in title, abstract, insights, and tags.

        Returns:
            A list of matching conversation entries.
        """
        query = query.lower()
        results = []
        for entry in self.index_data["conversations"]:
            # Search in title, abstract, and insights
            if query in entry["title"].lower() or \
               query in entry["abstract"].lower() or \
               any(query in insight.lower() for insight in entry.get("key_insights", [])):
                results.append(entry)
                continue # Move to next entry to avoid duplicates
            
            # Search in tags
            if any(query in tag.lower() for tag in entry.get("tags", [])):
                results.append(entry)

        return results

    def save(self):
        """Saves the index data back to its file."""
        save_yaml(self.index_data, self.filepath)
        print(f"✅ Chat index saved to {self.filepath}")

# Command-line interface
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Manage the master chat index.")
    parser.add_argument("index_file", help="Path to the master chat_index.yml file.")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'update' command
    update_parser = subparsers.add_parser("update", help="Add or update an entry from a chat history file.")
    update_parser.add_argument("history_file", help="Path to the chat_history.yml file to index.")
    update_parser.add_argument("--title", required=True, help="A descriptive title for the conversation.")
    update_parser.add_argument("--abstract", required=True, help="A paragraph summary of the conversation.")
    update_parser.add_argument("--insights", nargs='+', default=[], help="A list of key insights or take-aways.")
    update_parser.add_argument("--tags", nargs='+', default=[], help="A list of tags for searching.")

    # 'search' command
    search_parser = subparsers.add_parser("search", help="Search the index for conversations.")
    search_parser.add_argument("query", help="The term to search for.")

    args = parser.parse_args()

    manager = ChatIndexManager(args.index_file)

    if args.command == "update":
        manager.add_or_update_from_history(
            history_filepath=args.history_file,
            title=args.title,
            abstract=args.abstract,
            key_insights=args.insights,
            tags=args.tags
        )
    elif args.command == "search":
        search_results = manager.search(args.query)
        if search_results:
            print(f"\nFound {len(search_results)} match(es) for '{args.query}':")
            print("-" * 40)
            for result in search_results:
                print(f"Title: {result['title']}")
                print(f"  ID: {result['conversation_id']}")
                print(f"  Path: {result['file_path']}")
                print(f"  Tags: {', '.join(result['tags'])}")
                print(f"  Abstract: {result['abstract'][:150]}...")
                print("-" * 40)
        else:
            print(f"No results found for '{args.query}'.")

