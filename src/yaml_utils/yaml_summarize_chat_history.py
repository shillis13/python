#!/usr/bin/env python3
"""
Chat History Summarizer

This script processes a chat_history.yml file to prepare a structured
"briefing document" for an AI to analyze. It extracts key metadata,
concatenates the conversation, and creates helpful indexes for tags
and in-chat annotations.
"""

import yaml
import argparse
from pathlib import Path
from collections import Counter, defaultdict
import re
from datetime import datetime

# Assuming yaml_helpers.py is accessible
def load_yaml(filepath):
    """Loads a YAML file and handles errors."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return None

def get_conversation_duration(start_str, end_str):
    """Calculates the duration between two ISO 8601 timestamps."""
    try:
        # Handle different ISO 8601 formats by removing 'Z' if present
        start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        return str(end_time - start_time)
    except (ValueError, TypeError):
        return "N/A"

def generate_summary_brief(history_filepath: Path) -> str:
    """
    Analyzes a chat history file and generates a structured summary brief.
    """
    history_data = load_yaml(history_filepath)
    if not history_data:
        return f"Could not load or parse the history file at: {history_filepath}"

    metadata = history_data.get("metadata", {})
    sessions = history_data.get("chat_sessions", [])

    # --- Initialize data structures ---
    conv_id = metadata.get("conversation_id", "N/A")
    start_date = metadata.get("created", "N/A")
    last_update = metadata.get("last_updated", "N/A")
    duration = get_conversation_duration(start_date, last_update)
    
    total_messages = metadata.get("total_messages", 0)
    total_exchanges = metadata.get("total_exchanges", 0)
    num_sessions = len(sessions)
    
    all_attachments = []
    full_text_content = []
    tag_to_message_index = defaultdict(list)
    annotation_index = []

    # --- Process all messages ---
    for session in sessions:
        for message in session.get("messages", []):
            msg_id = message.get("message_id", "N/A")
            msg_num = message.get("message_number", 0)

            # Build full text content
            if message.get("role") in ["user", "assistant"]:
                full_text_content.append(f"[{message['role'].upper()} - Msg {msg_num}] {message['content']}")
            
            # Index attachments
            if message.get("attachments"):
                for attachment in message["attachments"]:
                    att_type = attachment.get("type", "unknown")
                    name = attachment.get("filename") or attachment.get("title") or attachment.get("artifact_id", "N/A")
                    all_attachments.append(f"- {att_type.capitalize()}: {name}")
            
            # Build tag and annotation indexes
            if message.get("tags"):
                for tag in message["tags"]:
                    tag_to_message_index[tag].append(msg_id)
                    # Check for our special annotation tag
                    if tag.lower() == '#key-insight':
                        annotation_index.append({
                            "message_id": msg_id,
                            "message_number": msg_num,
                            "content": message['content']
                        })

    # --- Perform keyword analysis ---
    all_text = " ".join(full_text_content)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
    # Exclude common but unhelpful words
    stop_words = {'this', 'that', 'with', 'what', 'have', 'from', 'your', 'like', 'just', 'about'}
    filtered_words = [word for word in words if word not in stop_words]
    common_words = [word for word, count in Counter(filtered_words).most_common(15)]

    # --- Assemble the Briefing Document ---
    brief = f"""
#======================================================================
# AI Briefing Document for Chat Indexing
#======================================================================

## 1. Conversation Metadata
- **Conversation ID:** {conv_id}
- **Date Range:** {start_date} to {last_update}
- **Total Duration:** {duration}
- **Statistics:** {total_messages} messages across {num_sessions} session(s).
- **Attachments/Artifacts Created:**
  {chr(10).join(all_attachments) if all_attachments else "  - None"}

## 2. In-Chat Annotations (Key Insights)
This section lists messages that were flagged during the conversation as being particularly important.

"""
    if annotation_index:
        for item in annotation_index:
            brief += f"- **Msg {item['message_number']} ({item['message_id']}):** {item['content'][:150]}...\n"
    else:
        brief += "- None found.\n"

    brief += f"""
## 3. Tag Index
This index maps every tag used in the conversation to the messages where it appears.

"""
    if tag_to_message_index:
        for tag, msg_ids in sorted(tag_to_message_index.items()):
            brief += f"- **{tag}** ({len(msg_ids)} mentions):\n  - {', '.join(msg_ids)}\n"
    else:
        brief += "- No tags found.\n"

    brief += f"""
## 4. Suggested Keywords (for Tag Curation)
- **Commonly Used Words:** {', '.join(common_words)}

#======================================================================
# Full Conversation Transcript for Analysis
#======================================================================

{chr(10).join(full_text_content)}
"""
    return brief.strip()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate a summary brief from a chat history file for AI analysis.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("history_file", help="Path to the chat_history.yml file.")
    parser.add_argument("-o", "--output", help="Optional. Path to save the summary brief to a text file.")
    
    args = parser.parse_args()

    summary_content = generate_summary_brief(Path(args.history_file))

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            print(f"✅ Summary brief saved to: {args.output}")
        except Exception as e:
            print(f"Error saving file: {e}")
    else:
        print(summary_content)

