#!/usr/bin/env python3
"""
HTML formatter for chat_history_v2.0 schema
Converts v2.0 JSON/YAML data to styled HTML format
"""

import html
from datetime import datetime
from typing import Dict, Any, List
import json


class HTMLFormatter:
    """Format v2.0 chat data as HTML."""
    
    def __init__(self, include_css: bool = True,
                 responsive: bool = True,
                 show_metadata: bool = True,
                 show_thinking: bool = True,
                 dark_mode: bool = False):
        """
        Initialize formatter with options.
        
        Args:
            include_css: Include CSS styling in output
            responsive: Make design mobile-responsive
            show_metadata: Show metadata section
            show_thinking: Show thinking blocks
            dark_mode: Use dark color scheme
        """
        self.include_css = include_css
        self.responsive = responsive
        self.show_metadata = show_metadata
        self.show_thinking = show_thinking
        self.dark_mode = dark_mode
    
    def format(self, chat_data: Dict[str, Any]) -> str:
        """
        Format v2.0 chat data as HTML.
        
        Args:
            chat_data: Chat data in v2.0 schema format
            
        Returns:
            Complete HTML document string
        """
        metadata = chat_data.get('metadata', {})
        messages = chat_data.get('messages', [])
        
        # Build HTML document
        parts = [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'    <title>{self._escape(metadata.get("title", "Chat History"))}</title>',
        ]
        
        if self.include_css:
            parts.append(self._generate_css())
        
        parts.extend([
            '</head>',
            f'<body class="{"dark-mode" if self.dark_mode else "light-mode"}">',
            '    <div class="container">',
        ])
        
        # Add header
        parts.append(self._format_header(metadata))
        
        # Add metadata section if requested
        if self.show_metadata:
            parts.append(self._format_metadata(metadata))
        
        # Add messages
        parts.append('        <div class="messages">')
        for message in messages:
            parts.append(self._format_message(message))
        parts.append('        </div>')
        
        # Close document
        parts.extend([
            '    </div>',
            '</body>',
            '</html>'
        ])
        
        return '\n'.join(parts)
    
    def _generate_css(self) -> str:
        """Generate CSS styles."""
        css = """
    <style>
        /* Reset and base styles */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }
        
        body.dark-mode {
            background-color: #1a1a1a;
            color: #e0e0e0;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header styles */
        header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        body.dark-mode header {
            background: #2a2a2a;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        h1 {
            font-size: 24px;
            margin-bottom: 10px;
            color: #333;
        }
        
        body.dark-mode h1 {
            color: #e0e0e0;
        }
        
        .subtitle {
            font-size: 14px;
            color: #666;
        }
        
        body.dark-mode .subtitle {
            color: #999;
        }
        
        /* Metadata section */
        .metadata {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        body.dark-mode .metadata {
            background: #2a2a2a;
        }
        
        .metadata-item {
            display: inline-block;
            margin-right: 20px;
            color: #666;
        }
        
        body.dark-mode .metadata-item {
            color: #999;
        }
        
        .metadata-item strong {
            color: #333;
        }
        
        body.dark-mode .metadata-item strong {
            color: #e0e0e0;
        }
        
        /* Messages */
        .messages {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        body.dark-mode .messages {
            background: #2a2a2a;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .message {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        
        body.dark-mode .message {
            border-bottom-color: #3a3a3a;
        }
        
        .message:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .message-role {
            font-weight: bold;
            font-size: 14px;
        }
        
        .message.user .message-role {
            color: #0066cc;
        }
        
        .message.assistant .message-role {
            color: #00aa00;
        }
        
        .message.system .message-role {
            color: #ff6600;
        }
        
        .message.tool .message-role {
            color: #9900ff;
        }
        
        body.dark-mode .message.user .message-role {
            color: #4da6ff;
        }
        
        body.dark-mode .message.assistant .message-role {
            color: #66ff66;
        }
        
        body.dark-mode .message.system .message-role {
            color: #ff9966;
        }
        
        body.dark-mode .message.tool .message-role {
            color: #cc99ff;
        }
        
        .message-timestamp {
            font-size: 12px;
            color: #999;
        }
        
        .message-content {
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        /* Code blocks */
        pre {
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 10px 0;
        }
        
        body.dark-mode pre {
            background: #1a1a1a;
        }
        
        code {
            background: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        }
        
        body.dark-mode code {
            background: #3a3a3a;
        }
        
        /* Thinking blocks */
        .thinking-block {
            margin-top: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            background: #f9f9f9;
        }
        
        body.dark-mode .thinking-block {
            border-color: #444;
            background: #1a1a1a;
        }
        
        .thinking-toggle {
            cursor: pointer;
            color: #0066cc;
            font-size: 14px;
            user-select: none;
        }
        
        body.dark-mode .thinking-toggle {
            color: #4da6ff;
        }
        
        .thinking-content {
            margin-top: 10px;
            padding-left: 20px;
            color: #666;
            display: none;
        }
        
        body.dark-mode .thinking-content {
            color: #999;
        }
        
        .thinking-content.show {
            display: block;
        }
        
        /* Attachments */
        .attachments {
            margin-top: 10px;
            padding: 10px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        
        body.dark-mode .attachments {
            background: #1a1a1a;
        }
        
        .attachment {
            display: inline-block;
            margin-right: 10px;
            margin-bottom: 5px;
            padding: 4px 8px;
            background: #e0e0e0;
            border-radius: 3px;
            font-size: 12px;
        }
        
        body.dark-mode .attachment {
            background: #3a3a3a;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            header, .messages, .metadata {
                padding: 15px;
            }
            
            h1 {
                font-size: 20px;
            }
            
            .message-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .message-timestamp {
                margin-top: 5px;
            }
        }
        
        /* Print styles */
        @media print {
            body {
                background: white;
                color: black;
            }
            
            .container {
                max-width: none;
                padding: 0;
            }
            
            header, .messages, .metadata {
                box-shadow: none;
                border: 1px solid #ddd;
                page-break-inside: avoid;
            }
            
            .thinking-toggle {
                display: none;
            }
            
            .thinking-content {
                display: block !important;
            }
        }
    </style>
"""
        return css
    
    def _format_header(self, metadata: Dict[str, Any]) -> str:
        """Format the header section."""
        title = self._escape(metadata.get('title', 'Chat History'))
        platform = metadata.get('platform', 'unknown')
        created = self._format_timestamp(metadata.get('created_at'))
        
        return f"""
        <header>
            <h1>{title}</h1>
            <div class="subtitle">
                <span>Platform: {platform}</span> | 
                <span>Created: {created}</span>
            </div>
        </header>
"""
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format the metadata section."""
        parts = ['        <div class="metadata">']
        
        # Chat ID
        if chat_id := metadata.get('chat_id'):
            parts.append(f'            <span class="metadata-item"><strong>Chat ID:</strong> {self._escape(chat_id)}</span>')
        
        # Statistics
        if stats := metadata.get('statistics'):
            if msg_count := stats.get('message_count'):
                parts.append(f'            <span class="metadata-item"><strong>Messages:</strong> {msg_count}</span>')
            if word_count := stats.get('word_count'):
                parts.append(f'            <span class="metadata-item"><strong>Words:</strong> {word_count:,}</span>')
            if duration := stats.get('duration_seconds'):
                duration_str = self._format_duration(duration)
                parts.append(f'            <span class="metadata-item"><strong>Duration:</strong> {duration_str}</span>')
        
        # Tags
        if tags := metadata.get('tags'):
            tags_str = ', '.join(self._escape(tag) for tag in tags)
            parts.append(f'            <span class="metadata-item"><strong>Tags:</strong> {tags_str}</span>')
        
        parts.append('        </div>')
        return '\n'.join(parts)
    
    def _format_message(self, message: Dict[str, Any]) -> str:
        """Format a single message."""
        role = message.get('role', 'unknown')
        content = self._escape(message.get('content', ''))
        timestamp = self._format_timestamp(message.get('timestamp'))
        message_id = message.get('message_id', '')
        
        parts = [f'            <div class="message {role}" id="{message_id}">']
        
        # Message header
        parts.append('                <div class="message-header">')
        parts.append(f'                    <span class="message-role">{role.title()}</span>')
        parts.append(f'                    <span class="message-timestamp">{timestamp}</span>')
        parts.append('                </div>')
        
        # Message content
        parts.append(f'                <div class="message-content">{content}</div>')
        
        # Platform-specific thinking
        if self.show_thinking and (thinking := message.get('platform_specific', {}).get('thinking')):
            parts.append(self._format_thinking_block(thinking))
        
        # Attachments
        if attachments := message.get('attachments'):
            parts.append(self._format_attachments(attachments))
        
        parts.append('            </div>')
        return '\n'.join(parts)
    
    def _format_thinking_block(self, thinking: str) -> str:
        """Format a collapsible thinking block."""
        # Generate unique ID for this block
        import random
        block_id = f"thinking_{random.randint(1000, 9999)}"
        
        return f"""
                <div class="thinking-block">
                    <div class="thinking-toggle" onclick="document.getElementById('{block_id}').classList.toggle('show')">
                        ▶ Show thinking process
                    </div>
                    <div id="{block_id}" class="thinking-content">
                        {self._escape(thinking)}
                    </div>
                </div>
"""
    
    def _format_attachments(self, attachments: List[Dict[str, Any]]) -> str:
        """Format message attachments."""
        if not attachments:
            return ""
        
        parts = ['                <div class="attachments">']
        
        for att in attachments:
            att_type = att.get('type', 'file')
            name = self._escape(att.get('name', 'unnamed'))
            
            icon = {
                'image': '🖼️',
                'code': '💻',
                'document': '📄',
                'file': '📎'
            }.get(att_type, '📎')
            
            parts.append(f'                    <span class="attachment">{icon} {name}</span>')
        
        parts.append('                </div>')
        return '\n'.join(parts)
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return "Unknown time"
        
        try:
            # Parse ISO timestamp
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            dt = datetime.fromisoformat(timestamp)
            # Format as readable string
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return timestamp
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def _escape(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return html.escape(str(text))


def format_as_html(chat_data: Dict[str, Any], **options) -> str:
    """
    Convenience function to format chat data as HTML.
    
    Args:
        chat_data: Chat data in v2.0 schema format
        **options: Options to pass to HTMLFormatter
        
    Returns:
        Complete HTML document string
    """
    formatter = HTMLFormatter(**options)
    return formatter.format(chat_data)