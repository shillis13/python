# Source Format Mappings to Chat History v2.0

**Version:** 2.0  
**Last Updated:** 2025-10-31  
**Purpose:** Reference guide for implementing converters from various export formats to the canonical v2.0 schema

---

## Overview

This document maps fields from each supported export format to the chat_history_v2.0 schema. Each section includes:
- Source field paths
- Target v2.0 field paths  
- Transformation logic
- Default values for missing fields
- Edge case handling

---

## 1. SaveMyChatbot Markdown → v2.0

**File Pattern:** `*.md` with YAML front matter

### Field Mappings

| Source Field/Pattern | Target v2.0 Field | Transformation |
|---------------------|-------------------|----------------|
| Front matter: `Exported on MM/DD/YYYY at HH:MM PM` | `metadata.exported_at` | Parse "10/25/2024 at 2:30 PM" → "2024-10-25T14:30:00Z" |
| Filename (if no title) | `metadata.title` | Remove extension, replace underscores with spaces |
| First occurrence in markdown | `metadata.created_at` | Use first message timestamp |
| Last occurrence in markdown | `metadata.updated_at` | Use last message timestamp |
| (not present) | `metadata.platform` | Infer from content patterns or use "unknown" |
| (constant) | `metadata.exporter` | "SaveMyChatbot" |
| `**You:**` prefix | `messages[].role` | "user" |
| `**ChatGPT:**` prefix | `messages[].role` | "assistant" |
| `**Claude:**` prefix | `messages[].role` | "assistant" |
| Message content after prefix | `messages[].content` | Strip prefix and leading whitespace |
| (generated) | `messages[].message_id` | `msg_{index:03d}` (e.g., msg_001) |
| (generated) | `messages[].timestamp` | Interpolate evenly between created_at and updated_at |
| Previous message ID | `messages[].parent_message_id` | ID of immediately preceding message |

### Default Values
```yaml
metadata:
  chat_id: "savemychatbot_{timestamp}_{hash6}"  # e.g., savemychatbot_20251031_a1b2c3
  platform: "chatgpt"  # or "claude" based on content
  session_info: null
  tags: []
  statistics:  # Compute from messages
    message_count: <count>
    word_count: <sum of words>
    token_count: <estimated>
```

### Edge Cases
- **Multiple "Exported on" lines**: Use the first occurrence
- **No role markers**: Alternate user/assistant starting with user
- **Empty messages**: Skip but log warning
- **Markdown in content**: Preserve as-is

---

## 2. Claude CLI JSON → v2.0

**File Pattern:** `*.json` with Claude CLI structure

### Field Mappings

| Source Field | Target v2.0 Field | Transformation |
|--------------|-------------------|----------------|
| `session_id` | `metadata.session_info.session_id` | Direct copy |
| `session_id` | `metadata.chat_id` | Use as-is or generate if missing |
| (constant) | `metadata.platform` | "claude-cli" |
| (constant) | `metadata.exporter` | "claude-cli" |
| `messages[0].timestamp` | `metadata.created_at` | First message timestamp |
| `messages[-1].timestamp` | `metadata.updated_at` | Last message timestamp |
| File modification time | `metadata.exported_at` | From filesystem |
| `messages[].role` | `messages[].role` | Direct copy |
| `messages[].content` | `messages[].content` | Direct copy |
| `messages[].timestamp` | `messages[].timestamp` | Ensure ISO 8601 format |
| `messages[].id` | `messages[].message_id` | Direct copy or generate |
| `messages[].model` | `messages[].platform_specific.model` | Move to platform_specific |
| `messages[].thinking` | `messages[].platform_specific.thinking` | Move to platform_specific |
| (index-based) | `messages[].parent_message_id` | Previous message ID |

### Default Values
```yaml
metadata:
  title: "Claude CLI Session {date}"
  tags: []
  statistics: # Compute from messages
```

### Edge Cases
- **Missing session_id**: Generate from timestamp
- **Non-ISO timestamps**: Convert to ISO 8601
- **Thinking blocks inline**: Extract to platform_specific.thinking

---

## 3. ChatGPT JSON Export → v2.0

**File Pattern:** `conversations.json` or individual conversation files

### Field Mappings

| Source Field | Target v2.0 Field | Transformation |
|--------------|-------------------|----------------|
| `id` or `conversation_id` | `metadata.chat_id` | Direct copy |
| `title` | `metadata.title` | Direct copy |
| (constant) | `metadata.platform` | "chatgpt" |
| (constant) | `metadata.exporter` | Detect from structure |
| `create_time` | `metadata.created_at` | Unix timestamp → ISO 8601 |
| `update_time` | `metadata.updated_at` | Unix timestamp → ISO 8601 |
| Export file date | `metadata.exported_at` | From filesystem or current time |
| `mapping[id].message.author.role` | `messages[].role` | Map: human→user, gpt→assistant |
| `mapping[id].message.content.parts[0]` | `messages[].content` | Join parts with newlines |
| `mapping[id].message.create_time` | `messages[].timestamp` | Unix timestamp → ISO 8601 |
| `mapping[id].id` | `messages[].message_id` | Direct copy |
| `mapping[id].parent` | Find parent message | Lookup parent ID in mapping |
| Parent's message_id | `messages[].parent_message_id` | After parent lookup |
| `mapping[id].message.metadata.model_slug` | `messages[].platform_specific.model` | e.g., "gpt-4" |

### Conversation Array Handling
```python
# For multi-conversation exports
for conversation in data:
    # Process each conversation separately
    # Each becomes its own v2.0 file
```

### Default Values
```yaml
metadata:
  tags: []
  session_info: null
  statistics: # Compute from mapping
```

### Edge Cases
- **Multi-part content**: Join `content.parts[]` with "\n"
- **Missing content.parts**: Use empty string
- **System messages**: Map system role directly
- **Deleted messages**: Skip if no content
- **Tool responses**: Check for `author.name` = "browser" or similar

---

## 4. Gemini Markdown → v2.0

**File Pattern:** `*.md` with specific Gemini formatting

### Field Mappings

| Source Pattern | Target v2.0 Field | Transformation |
|----------------|-------------------|----------------|
| Filename | `metadata.chat_id` | Slugify and add timestamp |
| Filename | `metadata.title` | Clean up filename |
| (constant) | `metadata.platform` | "gemini" |
| (constant) | `metadata.exporter` | "gemini-web" or detected |
| First message | `metadata.created_at` | Use current date or file date |
| Last message | `metadata.updated_at` | Use current date or file date |
| `## You` header | `messages[].role` | "user" |
| `## Gemini` header | `messages[].role` | "assistant" |
| Content under header | `messages[].content` | Until next header |
| (generated) | `messages[].message_id` | Sequential IDs |
| (interpolated) | `messages[].timestamp` | Distribute evenly |
| Previous message | `messages[].parent_message_id` | Sequential chain |

### Cleaning Logic
```python
# Remove "Show thinking" artifacts
content = re.sub(r'<details>.*?Show thinking.*?</details>', '', content, flags=re.DOTALL)
```

### Default Values
```yaml
metadata:
  exported_at: # File modification time
  tags: ["gemini-export"]
  session_info: null
```

### Edge Cases
- **Code blocks**: Preserve markdown formatting
- **Empty sections**: Create message with empty content
- **Multiple consecutive same-role messages**: Merge or keep separate based on context

---

## 5. Pipeline staged.json → v2.0

**File Pattern:** Pipeline intermediate format

### Field Mappings

| Source Field | Target v2.0 Field | Transformation |
|--------------|-------------------|----------------|
| `chat_id` | `metadata.chat_id` | Direct copy |
| `source.ai` | `metadata.platform` | Map to v2.0 platform enum |
| `source.exporter` | `metadata.exporter` | Direct copy |
| `timestamps.created_utc` | `metadata.created_at` | Ensure ISO format |
| `timestamps.updated_utc` | `metadata.updated_at` | Ensure ISO format |
| `timestamps.exported_utc` | `metadata.exported_at` | Ensure ISO format |
| `messages[].role` | `messages[].role` | Direct copy |
| `messages[].content` | `messages[].content` | Direct copy |
| `messages[].ts_utc` | `messages[].timestamp` | Rename field |
| Generate from index | `messages[].message_id` | If not present |
| (not present) | `messages[].parent_message_id` | Add based on sequence |

### Metadata Enrichment
```yaml
# Add computed fields not in staged format
metadata:
  title: # Extract from first user message or generate
  tags: []
  statistics: # Compute from messages
```

### Edge Cases
- **Missing timestamps**: Use file dates
- **Invalid platform names**: Map to "unknown"
- **Tool messages**: Already supported in staged format

---

## Common Transformation Functions

### Timestamp Parsing
```python
def parse_timestamp(value, format_hint=None):
    """Convert various timestamp formats to ISO 8601"""
    if isinstance(value, (int, float)):
        # Unix timestamp
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    elif "at" in value and ("AM" in value or "PM" in value):
        # SaveMyChatbot format: "10/25/2024 at 2:30 PM"
        return datetime.strptime(value, "%m/%d/%Y at %I:%M %p").isoformat() + "Z"
    # Add more format parsers as needed
    return value  # Assume already ISO 8601
```

### ID Generation
```python
def generate_chat_id(platform, timestamp, content_hash=None):
    """Generate unique chat ID"""
    ts = timestamp.replace(":", "").replace("-", "")[:8]
    if content_hash:
        return f"{platform}_{ts}_{content_hash[:6]}"
    return f"{platform}_{ts}_{uuid.uuid4().hex[:6]}"

def generate_message_id(index):
    """Generate sequential message ID"""
    return f"msg_{index:03d}"
```

### Statistics Computation
```python
def compute_statistics(messages):
    """Calculate conversation statistics"""
    word_count = sum(len(msg['content'].split()) for msg in messages)
    message_count = len(messages)
    
    # Rough token estimation (words * 1.3)
    token_count = int(word_count * 1.3)
    
    if len(messages) >= 2:
        duration = (parse_timestamp(messages[-1]['timestamp']) - 
                   parse_timestamp(messages[0]['timestamp'])).total_seconds()
    else:
        duration = 0
        
    return {
        'message_count': message_count,
        'word_count': word_count,
        'token_count': token_count,
        'duration_seconds': duration
    }
```

---

## Implementation Notes

1. **Platform Detection**: When platform is ambiguous, scan content for patterns:
   - "ChatGPT" in assistant messages → chatgpt
   - "Claude" in assistant messages → claude-desktop/web
   - Model names in metadata → infer platform

2. **Missing Required Fields**:
   - `chat_id`: Always generate if missing
   - `message_id`: Always generate if missing
   - `timestamp`: Use file date or interpolate
   - `created_at`/`updated_at`: Use first/last message or file dates

3. **Content Normalization**:
   - Trim leading/trailing whitespace
   - Preserve internal formatting and line breaks
   - Don't modify markdown or code blocks

4. **Error Handling**:
   - Log warnings for missing optional fields
   - Fail fast on missing required fields
   - Provide helpful error messages with field paths

5. **Performance**:
   - Process messages in order for parent_id assignment
   - Batch timestamp parsing for efficiency
   - Use streaming for large files (>10MB)

---

**Document Version:** 2.0  
**Schema Version:** 2.0  
**Status:** Reference implementation guide