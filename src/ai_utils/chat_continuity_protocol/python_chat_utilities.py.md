# python_chat_utilities.py Summary

## Purpose
Python equivalent of yaml_chat_utilities.js that properly leverages existing Python YAML utilities (helpers.py) for maintaining conversation history in YAML format. Provides CLI tools and programmatic interface for chat history management.

## Core Classes

### ChatHistoryManager
Main class for conversation tracking that reuses existing utilities:

**Initialization & ID Generation:**
- Uses `get_utc_timestamp()` from helpers.py for consistent timestamp format
- Generates conversation/session/message IDs following established patterns
- Auto-initializes structured metadata with version tracking

**File Operations:**
- `save_to_file()` / `load_from_file()` - Uses existing `save_yaml()` / `load_yaml()` functions
- `export_to_yaml()` / `export_for_handoff()` - YAML generation for session transitions
- Follows established error handling patterns from existing utilities

**Message Management:**
- `record_message(role, content, tags, attachments)` - Core message recording
- `record_claude_response(content, artifact_ids, tags)` - Specialized for Claude responses
- `add_file_attachment()` - Creates structured attachment objects
- Auto-calculates metadata (tokens, chars, words) following JS equivalent

**Session & Archive Management:**
- `start_new_session()` - Manages session transitions with proper linking
- `archive_conversation_section()` - Uses existing `archive_and_update_metadata()` function
- `import_previous_history()` - Merges previous conversation data

**Search & Analysis:**
- `search_content()` - Text search across message content
- `find_messages_by_tag()` - Tag-based message filtering
- `get_stats()` - Comprehensive conversation statistics

## Command-Line Interface
Follows existing utility patterns with argparse:
- `--init` - Initialize new chat history file
- `--add-message` - Add messages with role/content/tags
- `--export-handoff` - Export for session transitions
- `--stats` - Display conversation statistics
- `--search` - Search message content
- `--archive` - Archive conversation sections

## Integration Features
**Reuses Existing Utilities:**
- All timestamp generation via `get_utc_timestamp()`
- All file operations via `load_yaml()` / `save_yaml()`
- Archive functionality via `archive_and_update_metadata()`
- Error handling patterns from existing scripts
- CLI argument parsing style from existing utilities

**Convenience Functions:**
- `initialize_chat_history()` - Simple initialization
- `load_chat_history(filepath)` - Load from existing file

## Usage Pattern
Can be used both programmatically and via CLI, designed to maintain conversation history with proper archiving and versioning using established Python utility patterns.
