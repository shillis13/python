# yaml_chat_utilities.js Summary

## Purpose
JavaScript utility for maintaining conversation history in YAML format to work around chat message limits. Provides background tracking that automatically records messages and enables seamless handoff between sessions.

## Core Classes

### BackgroundChatHistory
Main class for conversation tracking with the following key features:

**Initialization:**
- Auto-generates conversation/session/message IDs using timestamp format
- Creates structured metadata with version tracking
- Initializes first session automatically

**Message Recording:**
- `recordMessage(role, content, tags, attachments)` - Records user/assistant messages
- `recordClaudeResponse(content, artifactIds, tags)` - Specialized for Claude responses
- Auto-calculates token estimates and metadata (char count, word count)
- Maintains sequential message numbering across sessions

**Session Management:**
- Tracks multiple chat sessions within one conversation
- Links sessions via `continued_from` relationships
- Supports session handoff when approaching usage limits

**Import/Export:**
- `exportToYaml()` - Standard YAML export
- `exportForHandoff()` - Special export for session transitions with instructions
- `importPreviousHistory()` - Merges previous conversation data

**Statistics & Monitoring:**
- `getStats()` - Returns message counts, token estimates, session info
- Tracks when approaching 15,000 token limit for handoff warnings

## Utility Features

### YamlUtils
Simple YAML serialization utility with `stringify()` method for browser-compatible YAML generation.

### Global Functions
- `initializeChatHistory()` - One-time session initialization
- `updateChatHistory()` - Called with each Claude response
- `getDownloadableHistory()` - Provides handoff-ready YAML

## Usage Pattern
Designed to run automatically in background - Claude calls `updateChatHistory()` with each response to maintain continuous conversation tracking without user intervention.
