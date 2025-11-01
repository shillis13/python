#!/usr/bin/env python3
"""
Markdown parser for various chat export formats
Handles ClaudeExporter, ChatGPTExporter, SaveMyChatbot, and generic markdown formats
"""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

from chat_processing.lib_converters.conversion_framework import BaseParser, ParserRegistry

logger = logging.getLogger(__name__)


class MarkdownParser(BaseParser):
    """Base markdown parser with common functionality."""
    
    def extract_yaml_frontmatter(self, content: str) -> tuple[Optional[Dict], str]:
        """Extract YAML frontmatter if present."""
        if content.strip().startswith('---'):
            try:
                import yaml
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    remaining_content = parts[2]
                    return frontmatter, remaining_content
            except:
                pass
        return None, content
    
    def parse_messages_generic(self, content: str, user_pattern: str, assistant_pattern: str) -> List[Dict[str, Any]]:
        """Parse messages using generic patterns."""
        messages = []
        current_message = None
        
        # Find all role markers and their positions
        combined_pattern = f"({user_pattern}|{assistant_pattern})"
        
        # Split content but keep track of what each part is
        parts = re.split(combined_pattern, content)
        
        for i in range(0, len(parts)):
            part = parts[i]
            if part is None:
                continue
                
            # Check if this part is a role marker
            if re.match(user_pattern, part):
                # Save previous message if exists
                if current_message and current_message.get('content'):
                    messages.append(current_message)
                # Start new message
                current_message = {
                    'message_id': f'msg_{len(messages)+1:03d}',
                    'role': 'user',
                    'content': '',
                    'timestamp': None
                }
            elif re.match(assistant_pattern, part):
                # Save previous message if exists
                if current_message and current_message.get('content'):
                    messages.append(current_message)
                # Start new message
                current_message = {
                    'message_id': f'msg_{len(messages)+1:03d}',
                    'role': 'assistant',
                    'content': '',
                    'timestamp': None
                }
            elif current_message is not None:
                # This is content for the current message
                content_part = part.strip()
                if content_part:
                    if current_message['content']:
                        current_message['content'] += '\n' + content_part
                    else:
                        current_message['content'] = content_part
        
        # Don't forget the last message
        if current_message and current_message.get('content'):
            messages.append(current_message)
        
        return messages


class SaveMyChatbotMarkdownParser(MarkdownParser):
    """Parser for SaveMyChatbot markdown exports."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'markdown' or not isinstance(content, str):
            return False
        
        # Check for SaveMyChatbot patterns
        return any([
            'SaveMyChatbot' in content,
            'export date:' in content.lower(),
            ('## User' in content and '## Assistant' in content),
            'Exported on' in content
        ])
    
    def parse(self, content: str, file_path: str = None) -> Dict[str, Any]:
        logger.info("Parsing SaveMyChatbot markdown format")
        
        # Extract frontmatter if present
        frontmatter, content = self.extract_yaml_frontmatter(content)
        
        # Initialize result
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        # Extract metadata from frontmatter or content
        metadata = result['metadata']
        
        # Try to extract export date
        export_match = re.search(r'Exported on (\d{2}/\d{2}/\d{4} at \d{1,2}:\d{2} [AP]M)', content)
        if export_match:
            metadata['exported_at'] = self._parse_timestamp(export_match.group(1), "%m/%d/%Y at %I:%M %p")
        elif frontmatter and 'export_date' in frontmatter:
            metadata['exported_at'] = self._parse_timestamp(frontmatter['export_date'])
        
        # Extract title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        elif file_path:
            from pathlib import Path
            metadata['title'] = Path(file_path).stem.replace('_', ' ')
        else:
            metadata['title'] = 'SaveMyChatbot Export'
        
        # Parse messages - SaveMyChatbot uses ## User and ## Assistant
        messages = []
        
        # Split by headers
        sections = re.split(r'^##\s+(User|Assistant)\s*$', content, flags=re.MULTILINE)
        
        current_role = None
        for section in sections:
            section = section.strip()
            
            if section in ['User', 'Assistant']:
                current_role = 'user' if section == 'User' else 'assistant'
            elif current_role and section:
                # Skip metadata sections
                if 'Exported on' not in section:
                    messages.append({
                        'message_id': f'msg_{len(messages)+1:03d}',
                        'role': current_role,
                        'content': section.strip(),
                        'timestamp': None
                    })
        
        # If no messages found with ## headers, try alternative patterns
        if not messages:
            messages = self.parse_messages_generic(content, r'\*\*User:\*\*', r'\*\*(Assistant|Claude):\*\*')
        
        # Interpolate timestamps
        if messages:
            now = datetime.now(timezone.utc)
            start_time = now.timestamp() - (len(messages) * 60)  # Assume 1 minute per message
            
            for i, msg in enumerate(messages):
                timestamp = datetime.fromtimestamp(start_time + (i * 60), tz=timezone.utc)
                msg['timestamp'] = timestamp.isoformat()
        
        result['messages'] = messages
        
        # Set metadata defaults
        metadata['platform'] = 'claude-web'  # SaveMyChatbot is typically Claude
        metadata['exporter'] = 'SaveMyChatbot'
        metadata['chat_id'] = self._generate_chat_id('claude', metadata.get('exported_at'))
        
        if messages:
            metadata['created_at'] = messages[0]['timestamp']
            metadata['updated_at'] = messages[-1]['timestamp']
        else:
            metadata['created_at'] = metadata.get('exported_at', datetime.now(timezone.utc).isoformat())
            metadata['updated_at'] = metadata['created_at']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "SaveMyChatbot Markdown"


class ChatGPTExporterMarkdownParser(MarkdownParser):
    """Parser for ChatGPT Exporter markdown format."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'markdown' or not isinstance(content, str):
            return False
        
        # Check for ChatGPT Exporter patterns
        return any([
            '## Prompt:' in content,
            '## Response:' in content,
            ('Created:' in content and 'Updated:' in content and 'Exported:' in content)
        ])
    
    def parse(self, content: str, file_path: str = None) -> Dict[str, Any]:
        logger.info("Parsing ChatGPT Exporter markdown format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract metadata from header
        created_match = re.search(r'Created:\s*(.+)', content)
        updated_match = re.search(r'Updated:\s*(.+)', content)
        exported_match = re.search(r'Exported:\s*(.+)', content)
        link_match = re.search(r'Link:\s*(.+)', content)
        
        if created_match:
            metadata['created_at'] = self._parse_timestamp(created_match.group(1).strip())
        if updated_match:
            metadata['updated_at'] = self._parse_timestamp(updated_match.group(1).strip())
        if exported_match:
            metadata['exported_at'] = self._parse_timestamp(exported_match.group(1).strip())
        
        # Extract title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        elif file_path:
            from pathlib import Path
            metadata['title'] = Path(file_path).stem.replace('_', ' ')
        else:
            metadata['title'] = 'ChatGPT Export'
        
        # Parse messages - ChatGPT Exporter uses ## Prompt: and ## Response:
        messages = []
        
        # Split by Prompt/Response headers
        sections = re.split(r'^##\s+(Prompt|Response):\s*$', content, flags=re.MULTILINE)
        
        current_role = None
        for section in sections:
            section = section.strip()
            
            if section == 'Prompt':
                current_role = 'user'
            elif section == 'Response':
                current_role = 'assistant'
            elif current_role and section and not section.startswith('Created:'):
                messages.append({
                    'message_id': f'msg_{len(messages)+1:03d}',
                    'role': current_role,
                    'content': section.strip(),
                    'timestamp': None
                })
        
        # Interpolate timestamps between created and updated
        if messages and metadata.get('created_at') and metadata.get('updated_at'):
            try:
                start_dt = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(metadata['updated_at'].replace('Z', '+00:00'))
                
                time_diff = (end_dt - start_dt).total_seconds()
                interval = time_diff / max(len(messages) - 1, 1)
                
                for i, msg in enumerate(messages):
                    timestamp = start_dt.timestamp() + (i * interval)
                    msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            except:
                # Fallback to simple interpolation
                now = datetime.now(timezone.utc)
                for i, msg in enumerate(messages):
                    msg['timestamp'] = now.isoformat()
        
        result['messages'] = messages
        
        # Set metadata defaults
        metadata['platform'] = 'chatgpt'
        metadata['exporter'] = 'ChatGPT Exporter'
        metadata['chat_id'] = self._generate_chat_id('chatgpt', metadata.get('created_at'))
        
        # Ensure required timestamps
        if not metadata.get('created_at'):
            metadata['created_at'] = messages[0]['timestamp'] if messages else datetime.now(timezone.utc).isoformat()
        if not metadata.get('updated_at'):
            metadata['updated_at'] = messages[-1]['timestamp'] if messages else metadata['created_at']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "ChatGPT Exporter Markdown"


class GenericMarkdownParser(MarkdownParser):
    """Generic markdown parser for various formats."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        # This parser is a fallback for any markdown format
        return format == 'markdown' and isinstance(content, str)
    
    def parse(self, content: str, file_path: str = None) -> Dict[str, Any]:
        logger.info("Parsing generic markdown format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract any frontmatter
        frontmatter, content = self.extract_yaml_frontmatter(content)
        
        # Try to extract title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        elif frontmatter and 'title' in frontmatter:
            metadata['title'] = frontmatter['title']
        elif file_path:
            from pathlib import Path
            metadata['title'] = Path(file_path).stem.replace('_', ' ')
        else:
            metadata['title'] = 'Untitled Conversation'
        
        # Try different message patterns
        messages = []
        
        # Pattern 1: **Role:**
        pattern1_messages = self.parse_messages_generic(
            content, 
            r'\*\*(User|You|Human):\*\*',
            r'\*\*(Assistant|Claude|ChatGPT|AI|Bot):\*\*'
        )
        
        if pattern1_messages:
            messages = pattern1_messages
        else:
            # Pattern 2: ### Role or ## Role
            sections = re.split(r'^#{2,3}\s+(User|Assistant|You|Claude|ChatGPT|Human|AI)\s*$', 
                              content, flags=re.MULTILINE)
            
            current_role = None
            for section in sections:
                section = section.strip()
                
                if section in ['User', 'You', 'Human']:
                    current_role = 'user'
                elif section in ['Assistant', 'Claude', 'ChatGPT', 'AI']:
                    current_role = 'assistant'
                elif current_role and section:
                    messages.append({
                        'message_id': f'msg_{len(messages)+1:03d}',
                        'role': current_role,
                        'content': section.strip(),
                        'timestamp': None
                    })
        
        # Generate timestamps
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(messages):
            # Simple timestamp generation - 1 minute apart
            timestamp = now.timestamp() - ((len(messages) - i) * 60)
            msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        
        result['messages'] = messages
        
        # Try to infer platform from content
        content_lower = content.lower()
        if 'claude' in content_lower:
            metadata['platform'] = 'claude-desktop'
        elif 'chatgpt' in content_lower or 'gpt' in content_lower:
            metadata['platform'] = 'chatgpt'
        else:
            metadata['platform'] = 'unknown'
        
        metadata['exporter'] = 'unknown'
        metadata['chat_id'] = self._generate_chat_id(metadata['platform'])
        
        if messages:
            metadata['created_at'] = messages[0]['timestamp']
            metadata['updated_at'] = messages[-1]['timestamp']
        else:
            metadata['created_at'] = datetime.now(timezone.utc).isoformat()
            metadata['updated_at'] = metadata['created_at']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "Generic Markdown"


# Register parsers
ParserRegistry.register('savemychatbot-markdown', SaveMyChatbotMarkdownParser)
ParserRegistry.register('chatgpt-exporter-markdown', ChatGPTExporterMarkdownParser)
ParserRegistry.register('generic-markdown', GenericMarkdownParser)