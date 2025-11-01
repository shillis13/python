#!/usr/bin/env python3
"""
HTML parser for chat exports
Handles Claude and ChatGPT HTML exports
"""

import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging

from ..conversion_framework import BaseParser, ParserRegistry

logger = logging.getLogger(__name__)


class ChatHTMLParser(HTMLParser):
    """HTML parser to extract chat messages."""
    
    def __init__(self):
        super().__init__()
        self.messages = []
        self.current_message = None
        self.current_role = None
        self.in_message = False
        self.in_role = False
        self.in_content = False
        self.current_data = []
        self.metadata = {}
        self.in_title = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        # Look for title
        if tag == 'title':
            self.in_title = True
        
        # Look for message containers
        if tag == 'div' and 'class' in attrs_dict:
            classes = attrs_dict['class']
            
            # Claude patterns
            if 'chat-message' in classes or 'message' in classes:
                self.in_message = True
                self.current_message = {
                    'content': '',
                    'role': None
                }
            elif 'message-role' in classes or 'role' in classes:
                self.in_role = True
            elif 'message-content' in classes or 'content' in classes:
                self.in_content = True
                
            # ChatGPT patterns
            elif 'user-message' in classes or 'user' in classes:
                self.in_message = True
                self.current_message = {
                    'content': '',
                    'role': 'user'
                }
                self.in_content = True
            elif 'assistant-message' in classes or 'assistant' in classes:
                self.in_message = True
                self.current_message = {
                    'content': '',
                    'role': 'assistant'
                }
                self.in_content = True
    
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
            if self.current_data:
                self.metadata['title'] = ' '.join(self.current_data).strip()
                self.current_data = []
        
        elif tag == 'div':
            if self.in_content:
                self.in_content = False
                if self.current_message and self.current_data:
                    content = ' '.join(self.current_data).strip()
                    self.current_message['content'] = content
                    self.current_data = []
            
            if self.in_role:
                self.in_role = False
                if self.current_data:
                    role_text = ' '.join(self.current_data).strip().lower()
                    if 'user' in role_text or 'human' in role_text or 'you' in role_text:
                        self.current_role = 'user'
                    elif 'assistant' in role_text or 'claude' in role_text or 'ai' in role_text or 'chatgpt' in role_text:
                        self.current_role = 'assistant'
                    
                    if self.current_message:
                        self.current_message['role'] = self.current_role
                    self.current_data = []
            
            if self.in_message:
                self.in_message = False
                if self.current_message and self.current_message.get('content'):
                    # Set role if not already set
                    if not self.current_message.get('role'):
                        self.current_message['role'] = self.current_role or 'user'
                    
                    self.messages.append(self.current_message)
                    self.current_message = None
    
    def handle_data(self, data):
        if self.in_title or self.in_role or self.in_content:
            self.current_data.append(data)


class GenericHTMLParser(BaseParser):
    """Generic HTML parser for chat exports."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'html' or not isinstance(content, str):
            return False
        
        # Basic HTML check
        return bool(re.search(r'<html|<!DOCTYPE', content, re.IGNORECASE))
    
    def parse(self, content: str, file_path: str = None) -> Dict[str, Any]:
        logger.info("Parsing HTML format")
        
        # Use custom HTML parser
        parser = ChatHTMLParser()
        parser.feed(content)
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract metadata
        metadata['title'] = parser.metadata.get('title', 'HTML Chat Export')
        
        # Try to detect platform from content
        content_lower = content.lower()
        if 'claude' in content_lower:
            metadata['platform'] = 'claude-desktop'
            metadata['exporter'] = 'claude-exporter-html'
        elif 'chatgpt' in content_lower:
            metadata['platform'] = 'chatgpt'
            metadata['exporter'] = 'chatgpt-exporter-html'
        else:
            metadata['platform'] = 'unknown'
            metadata['exporter'] = 'unknown-html'
        
        # If no messages found via parser, try regex patterns
        if not parser.messages:
            messages = self._parse_with_regex(content)
        else:
            messages = []
            for i, msg_data in enumerate(parser.messages):
                messages.append({
                    'message_id': f'msg_{i+1:03d}',
                    'role': msg_data['role'],
                    'content': self._clean_html_content(msg_data['content']),
                    'timestamp': None
                })
        
        # Generate timestamps
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(messages):
            if not msg.get('timestamp'):
                # Simple timestamp generation - work backwards from now
                timestamp = now.timestamp() - ((len(messages) - i) * 60)
                msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            
            # Add parent reference
            if i > 0:
                msg['parent_message_id'] = messages[i-1]['message_id']
        
        result['messages'] = messages
        
        # Generate chat_id
        metadata['chat_id'] = self._generate_chat_id(metadata['platform'])
        
        # Set timestamps
        if messages:
            metadata['created_at'] = messages[0]['timestamp']
            metadata['updated_at'] = messages[-1]['timestamp']
        else:
            now_iso = datetime.now(timezone.utc).isoformat()
            metadata['created_at'] = now_iso
            metadata['updated_at'] = now_iso
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def _parse_with_regex(self, content: str) -> List[Dict[str, Any]]:
        """Fallback regex-based parsing."""
        messages = []
        
        # Try to find message containers with content
        # Look for div with class="message [role]" followed by nested content
        pattern1 = re.compile(
            r'<div[^>]*class=["\']message\s+(user|assistant)["\'][^>]*>.*?<div[^>]*class=["\']message-content["\'][^>]*>(.*?)</div>',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern1.finditer(content):
            role = match.group(1).lower()
            content_html = match.group(2)
            
            # Clean content
            content_text = self._clean_html_content(content_html)
            
            if content_text.strip():
                messages.append({
                    'message_id': f'msg_{len(messages)+1:03d}',
                    'role': role,
                    'content': content_text,
                    'timestamp': None
                })
        
        # If no messages found with the specific pattern, try a more general one
        if not messages:
            # Pattern 2: <div class="[something with user/assistant]">content</div>
            # But exclude message-header, message-role, etc.
            pattern2 = re.compile(
                r'<div[^>]*class=["\'](?!.*(?:header|role|timestamp))([^"\']*\b(?:user|assistant)\b[^"\']*)["\'][^>]*>(.*?)</div>',
                re.IGNORECASE | re.DOTALL
            )
            
            for match in pattern2.finditer(content):
                classes = match.group(1).lower()
                content_html = match.group(2)
                
                # Skip if content contains nested message structure
                if '<div' in content_html and 'message-' in content_html:
                    continue
                
                # Determine role
                if 'user' in classes:
                    role = 'user'
                elif 'assistant' in classes:
                    role = 'assistant'
                else:
                    continue
                
                # Clean content
                content_text = self._clean_html_content(content_html)
                
                if content_text.strip() and len(content_text) > 10:  # Skip very short content
                    messages.append({
                        'message_id': f'msg_{len(messages)+1:03d}',
                        'role': role,
                        'content': content_text,
                        'timestamp': None
                    })
        
        # If no messages found, try simpler patterns
        if not messages:
            # Pattern 2: Look for User: and Assistant: markers
            text_content = self._clean_html_content(content)
            
            # Split by role markers
            parts = re.split(r'(User:|Assistant:|Human:|AI:|You:|Claude:|ChatGPT:)', text_content)
            
            current_role = None
            for part in parts:
                part = part.strip()
                
                if part in ['User:', 'Human:', 'You:']:
                    current_role = 'user'
                elif part in ['Assistant:', 'AI:', 'Claude:', 'ChatGPT:']:
                    current_role = 'assistant'
                elif current_role and part:
                    messages.append({
                        'message_id': f'msg_{len(messages)+1:03d}',
                        'role': current_role,
                        'content': part,
                        'timestamp': None
                    })
        
        return messages
    
    def _clean_html_content(self, html: str) -> str:
        """Remove HTML tags and clean up content."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace <br> with newlines
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        
        # Replace <p> with double newlines
        html = re.sub(r'</p>', '\n\n', html, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Decode HTML entities
        import html as html_module
        text = html_module.unescape(html)
        
        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
    
    def get_source_name(self) -> str:
        return "HTML Export"


# Register parser
ParserRegistry.register('generic-html', GenericHTMLParser)