#!/usr/bin/env python3
"""
Markdown formatter for chat_history_v2.0 schema
Converts v2.0 JSON/YAML data to human-readable Markdown format
"""

import yaml
from datetime import datetime
from typing import Dict, Any, List
import re


class MarkdownFormatter:
    """Format v2.0 chat data as Markdown."""
    
    def __init__(self, include_metadata_frontmatter: bool = True,
                 group_by_timestamp: bool = True,
                 show_thinking: bool = True):
        """
        Initialize formatter with options.
        
        Args:
            include_metadata_frontmatter: Include YAML front matter
            group_by_timestamp: Group messages by timestamp sections
            show_thinking: Show thinking blocks in collapsible sections
        """
        self.include_metadata_frontmatter = include_metadata_frontmatter
        self.group_by_timestamp = group_by_timestamp
        self.show_thinking = show_thinking
    
    def format(self, chat_data: Dict[str, Any]) -> str:
        """
        Format v2.0 chat data as Markdown.
        
        Args:
            chat_data: Chat data in v2.0 schema format
            
        Returns:
            Formatted Markdown string
        """
        parts = []
        
        # Add front matter if requested
        if self.include_metadata_frontmatter:
            parts.append(self._format_frontmatter(chat_data.get('metadata', {})))
        
        # Add title
        title = chat_data.get('metadata', {}).get('title', 'Untitled Chat')
        parts.append(f"# {title}\n")
        
        # Add metadata summary if not in front matter
        if not self.include_metadata_frontmatter:
            parts.append(self._format_metadata_section(chat_data.get('metadata', {})))
        
        # Format messages
        messages = chat_data.get('messages', [])
        if self.group_by_timestamp:
            parts.append(self._format_messages_grouped(messages))
        else:
            parts.append(self._format_messages_sequential(messages))
        
        return '\n'.join(parts)
    
    def _format_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Format metadata as YAML front matter."""
        # Select key fields for front matter
        frontmatter = {
            'title': metadata.get('title', 'Untitled Chat'),
            'chat_id': metadata.get('chat_id'),
            'platform': metadata.get('platform'),
            'created_at': metadata.get('created_at'),
            'updated_at': metadata.get('updated_at'),
            'exported_at': metadata.get('exported_at'),
            'exporter': metadata.get('exporter'),
            'tags': metadata.get('tags', [])
        }
        
        # Remove None values
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}
        
        # Convert to YAML
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        
        return f"---\n{yaml_str}---\n"
    
    def _format_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """Format metadata as a readable section."""
        lines = ["## Metadata\n"]
        
        if metadata.get('platform'):
            lines.append(f"**Platform:** {metadata['platform']}")
        
        if metadata.get('created_at'):
            created = self._format_timestamp(metadata['created_at'])
            lines.append(f"**Created:** {created}")
        
        if metadata.get('updated_at'):
            updated = self._format_timestamp(metadata['updated_at'])
            lines.append(f"**Updated:** {updated}")
        
        if metadata.get('statistics'):
            stats = metadata['statistics']
            lines.append(f"**Messages:** {stats.get('message_count', 0)}")
            lines.append(f"**Words:** {stats.get('word_count', 0)}")
        
        return '\n'.join(lines) + '\n'
    
    def _format_messages_grouped(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages grouped by timestamp."""
        if not messages:
            return ""
        
        parts = []
        current_group = []
        last_timestamp = None
        
        for msg in messages:
            msg_timestamp = self._parse_timestamp(msg.get('timestamp'))
            
            # Check if we should start a new group (> 5 minutes apart)
            if last_timestamp and msg_timestamp:
                time_diff = abs((msg_timestamp - last_timestamp).total_seconds())
                if time_diff > 300:  # 5 minutes
                    # Output current group
                    if current_group:
                        parts.append(self._format_message_group(current_group))
                        current_group = []
            
            current_group.append(msg)
            last_timestamp = msg_timestamp
        
        # Output final group
        if current_group:
            parts.append(self._format_message_group(current_group))
        
        return '\n'.join(parts)
    
    def _format_message_group(self, messages: List[Dict[str, Any]]) -> str:
        """Format a group of messages under a timestamp header."""
        if not messages:
            return ""
        
        # Use first message timestamp for group header
        timestamp = messages[0].get('timestamp')
        header = self._format_timestamp(timestamp)
        
        parts = [f"## {header}\n"]
        
        for msg in messages:
            parts.append(self._format_single_message(msg))
        
        return '\n'.join(parts)
    
    def _format_messages_sequential(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages sequentially without grouping."""
        parts = []
        
        for msg in messages:
            # Add timestamp as small header
            timestamp = self._format_timestamp(msg.get('timestamp'))
            parts.append(f"### {timestamp}\n")
            parts.append(self._format_single_message(msg))
        
        return '\n'.join(parts)
    
    def _format_single_message(self, message: Dict[str, Any]) -> str:
        """Format a single message."""
        role = message.get('role', 'unknown').title()
        content = message.get('content', '')
        
        # Handle special roles
        if role == 'System':
            parts = [f"*System: {content}*\n"]
        elif role == 'Tool':
            parts = [f"*Tool Output:*\n```\n{content}\n```\n"]
        elif role == 'Thinking':
            # Format thinking as collapsible section
            if self.show_thinking:
                parts = [
                    "<details>",
                    "<summary>Thinking Process</summary>\n",
                    content,
                    "\n</details>\n"
                ]
            else:
                parts = []  # Skip thinking blocks
        else:
            # Regular user/assistant message
            parts = [f"**{role}:**\n{content}\n"]
        
        # Handle attachments
        attachments = message.get('attachments', [])
        if attachments:
            parts.append(self._format_attachments(attachments))
        
        # Handle platform-specific data
        if message.get('platform_specific', {}).get('thinking') and self.show_thinking:
            thinking = message['platform_specific']['thinking']
            parts.append(
                "<details>\n"
                "<summary>Thinking Process</summary>\n\n"
                f"{thinking}\n"
                "</details>\n"
            )
        
        return '\n'.join(parts)
    
    def _format_attachments(self, attachments: List[Dict[str, Any]]) -> str:
        """Format message attachments."""
        if not attachments:
            return ""
        
        parts = ["*Attachments:*"]
        
        for att in attachments:
            att_type = att.get('type', 'file')
            name = att.get('name', 'unnamed')
            
            if att_type == 'image':
                # Format as markdown image if URL available
                if url := att.get('url'):
                    parts.append(f"- ![{name}]({url})")
                else:
                    parts.append(f"- Image: {name}")
            elif att_type == 'code':
                # Format code attachment
                content = att.get('content', '')
                if content:
                    parts.append(f"- Code: `{name}`\n```\n{content}\n```")
                else:
                    parts.append(f"- Code: {name}")
            else:
                # Generic attachment
                parts.append(f"- {att_type.title()}: {name}")
        
        return '\n'.join(parts) + '\n'
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return "Unknown time"
        
        try:
            dt = self._parse_timestamp(timestamp)
            # Format as readable string
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            # Return as-is if parsing fails
            return timestamp
    
    def _parse_timestamp(self, timestamp: str) -> datetime:
        """Parse ISO timestamp to datetime."""
        if not timestamp:
            return None
        
        try:
            # Handle ISO format with Z suffix
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp)
        except:
            return None
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special Markdown characters in text."""
        # Characters that need escaping in Markdown
        special_chars = r'\\`*_{}[]()#+-.!|'
        
        # Escape each special character
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text


def format_as_markdown(chat_data: Dict[str, Any], **options) -> str:
    """
    Convenience function to format chat data as Markdown.
    
    Args:
        chat_data: Chat data in v2.0 schema format
        **options: Options to pass to MarkdownFormatter
        
    Returns:
        Formatted Markdown string
    """
    formatter = MarkdownFormatter(**options)
    return formatter.format(chat_data)