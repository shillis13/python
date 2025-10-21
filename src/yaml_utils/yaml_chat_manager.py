#!/usr/bin/env python3
"""
ChatHistoryManager

A Python class to manage the lifecycle of a chat history, including session
tracking, message recording, and file I/O, conforming to the defined
chat history schema.
"""

import yaml
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Assume yaml_helpers.py is in the same directory or accessible in the path
# from yaml_helpers import load_yaml, save_yaml


# For self-containment, we'll include the helper functions here.
# Load a YAML file and handle errors.
def load_yaml(filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Loads a YAML file and handles errors."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'")
        return None
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


# Manage the creation, modification, and persistence of chat history files.
class ChatHistoryManager:
    """
    Manages the creation, modification, and persistence of a chat history.
    """

    def __init__(
        self,
        filepath: Optional[Union[str, Path]] = None,
        platform: str = "gemini",
        model_version: Optional[str] = None,
    ):
        """
        Initializes the ChatHistoryManager.

        Args:
            filepath: Path to an existing chat history file to load.
                      If None, a new history is created in memory.
            platform: The name of the AI platform being used (e.g., 'gemini').
            model_version: The specific version of the model being used.
        """
        self.filepath = Path(filepath) if filepath else None
        self.platform = platform
        self.model_version = model_version
        self.last_message_id: Optional[str] = None

        if self.filepath and self.filepath.exists():
            self.history_data = load_yaml(self.filepath)
            if not self.history_data:
                raise ValueError(
                    f"Failed to load or parse chat history from {self.filepath}"
                )
            self._sync_state_from_loaded_data()
        else:
            self.history_data = self._initialize_new_history()

        self.current_session_id = self.history_data["chat_sessions"][-1]["session_id"]

    def _generate_id(self, prefix: str) -> str:
        """Generates a unique ID with a timestamp and random suffix."""
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid.uuid4().hex[:5]
        return f"{prefix}_{now}_{suffix}"

    def _initialize_new_history(self) -> Dict[str, Any]:
        """Creates the basic structure for a new chat history."""
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conv_id = self._generate_id("conv")
        session_id = self._generate_id("session")

        return {
            "metadata": {
                "conversation_id": conv_id,
                "created": now_iso,
                "last_updated": now_iso,
                "version": 1,
                "total_messages": 0,
                "total_exchanges": 0,
                "tags": [],
                "format_version": "1.1",
            },
            "chat_sessions": [
                {
                    "session_id": session_id,
                    "started": now_iso,
                    "ended": None,
                    "platform": self.platform,
                    "model_version": self.model_version,
                    "continued_from": None,
                    "tags": ["initial-session"],
                    "messages": [],
                }
            ],
        }

    def _sync_state_from_loaded_data(self):
        """Updates internal state variables after loading a history file."""
        if not self.history_data.get("chat_sessions"):
            # If file is corrupt or empty, re-initialize
            self.history_data = self._initialize_new_history()
            return

        last_session = self.history_data["chat_sessions"][-1]
        if last_session.get("messages"):
            self.last_message_id = last_session["messages"][-1]["message_id"]
        else:
            # Find the last message from a previous session if the current one is empty
            for session in reversed(self.history_data["chat_sessions"]):
                if session.get("messages"):
                    self.last_message_id = session["messages"][-1]["message_id"]
                    break

    def _get_current_session(self) -> Optional[Dict[str, Any]]:
        """Finds and returns the current active session object."""
        for session in reversed(self.history_data["chat_sessions"]):
            if session["session_id"] == self.current_session_id:
                return session
        return None

    def record_message(
        self,
        role: str,
        content: str,
        attachments: Optional[List[Dict]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Records a new message to the current session and updates metadata.

        Args:
            role: The role of the message author ('user' or 'assistant').
            content: The text content of the message.
            attachments: A list of attachment dictionaries.
            tags: A list of tags for the message.

        Returns:
            The message_id of the newly created message.
        """
        if role not in ["user", "assistant", "system"]:
            raise ValueError("Role must be 'user', 'assistant', or 'system'.")

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Update conversation metadata
        meta = self.history_data["metadata"]
        meta["last_updated"] = now_iso
        meta["version"] += 1
        meta["total_messages"] += 1
        if role == "assistant":
            meta["total_exchanges"] += 1

        # Create the new message object
        message_id = self._generate_id("msg")
        new_message = {
            "message_id": message_id,
            "message_number": meta["total_messages"],
            "parent_message_id": self.last_message_id if role == "assistant" else None,
            "conversation_id": meta["conversation_id"],
            "session_id": self.current_session_id,
            "timestamp": now_iso,
            "role": role,
            "content": content,
            "attachments": attachments or [],
            "tags": tags or [],
            "metadata": {
                "char_count": len(content),
                "word_count": len(content.split()),
                "estimated_tokens": int(len(content) / 4),  # A rough estimate
            },
        }

        # Add message to the current session
        current_session = self._get_current_session()
        if current_session:
            current_session["messages"].append(new_message)
        else:
            # This should not happen in a normal flow
            raise RuntimeError(
                f"Could not find current session with ID {self.current_session_id}"
            )

        # Update the last message ID
        self.last_message_id = message_id

        return message_id

    def start_new_session(self) -> str:
        """
        Ends the current session and starts a new one within the same conversation.

        Returns:
            The session_id of the newly created session.
        """
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # End the current session
        current_session = self._get_current_session()
        if current_session:
            current_session["ended"] = now_iso

        # Create a new session
        previous_session_id = self.current_session_id
        new_session_id = self._generate_id("session")

        new_session = {
            "session_id": new_session_id,
            "started": now_iso,
            "ended": None,
            "platform": self.platform,
            "model_version": self.model_version,
            "continued_from": previous_session_id,
            "tags": [],
            "messages": [],
        }

        self.history_data["chat_sessions"].append(new_session)
        self.current_session_id = new_session_id

        # Update conversation metadata
        self.history_data["metadata"]["version"] += 1
        self.history_data["metadata"]["last_updated"] = now_iso

        return new_session_id

    def save(self, custom_filepath: Optional[Union[str, Path]] = None) -> None:
        """
        Saves the current chat history to a YAML file.

        Args:
            custom_filepath: If provided, saves to this path. Otherwise, uses
                             the path provided during initialization.
        """
        save_path = Path(custom_filepath) if custom_filepath else self.filepath
        if not save_path:
            raise ValueError("No filepath specified for saving.")

        save_yaml(self.history_data, save_path)
        print(f"✅ Chat history saved to {save_path}")

    def get_history_as_dict(self) -> Dict[str, Any]:
        """Returns the current history data as a dictionary."""
        return self.history_data


# Example Usage (can be run directly for testing)
if __name__ == "__main__":
    # --- Test Case 1: Create a new history from scratch ---
    print("--- Running Test Case 1: New History ---")
    chat_manager = ChatHistoryManager(platform="gemini", model_version="1.5-pro-latest")

    # Record a user message
    chat_manager.record_message(
        role="user",
        content="Hello, please help me with a Python script.",
        tags=["python", "initial-request"],
    )

    # Record an assistant response
    chat_manager.record_message(
        role="assistant",
        content="Of course! What would you like the Python script to do?",
        attachments=[
            {
                "type": "artifact",
                "artifact_id": "placeholder_script_1",
                "artifact_type": "code",
                "title": "Initial Script Placeholder",
                "created_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "status": "in-progress",
            }
        ],
    )

    # Start a new session
    chat_manager.start_new_session()

    # Record another user message in the new session
    chat_manager.record_message(
        role="user",
        content="I need it to parse a YAML file and extract all keys.",
        tags=["yaml", "parsing"],
    )

    # Save the file
    output_path = Path("test_chat_history.yml")
    chat_manager.save(output_path)

    # --- Test Case 2: Load the history we just saved ---
    print("\n--- Running Test Case 2: Loading History ---")
    if output_path.exists():
        loaded_manager = ChatHistoryManager(filepath=output_path)
        print(
            "Loaded conversation ID:",
            loaded_manager.history_data["metadata"]["conversation_id"],
        )
        print(
            "Total messages loaded:",
            loaded_manager.history_data["metadata"]["total_messages"],
        )

        # Add one more message
        loaded_manager.record_message(
            role="assistant", content="Excellent, I can help with that."
        )
        loaded_manager.save()

        print("\nFinal state of loaded history:")
        print(
            yaml.dump(loaded_manager.get_history_as_dict(), indent=2, sort_keys=False)
        )

        # Clean up the test file
        output_path.unlink()
