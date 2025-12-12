#!/usr/bin/env python3
"""
YAML parser for chat exports
Handles Claude exporter YAML outputs and generic YAML formats
"""

import yaml
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

from ai_utils.chat_processing.lib_converters.conversion_framework import BaseParser, ParserRegistry

logger = logging.getLogger(__name__)


class GenericYAMLParser(BaseParser):
    """Generic YAML parser for chat exports."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        # YAML content is loaded as dict/list by the framework
        return format == 'yaml' and isinstance(content, (dict, list))
    
    def parse(self, content: Any, file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing YAML format")
        
        # Handle list format (some exports might be arrays)
        if isinstance(content, list):
            # Assume it's a list of messages
            content = {'messages': content}
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Check if content already has v2.0 structure
        if content.get('schema_version') == '2.0':
            # Already in correct format, just return it
            return content
        
        # Extract metadata - check common locations
        if 'metadata' in content and isinstance(content['metadata'], dict):
            source_metadata = content['metadata']
            
            # Copy over relevant fields
            metadata['title'] = source_metadata.get('title', content.get('title', 'Untitled Conversation'))
            
            # Handle dates
            for field in ['created_at', 'created', 'create_time']:
                if field in source_metadata:
                    metadata['created_at'] = self._parse_timestamp(source_metadata[field])
                    break
            
            for field in ['updated_at', 'updated', 'update_time']:
                if field in source_metadata:
                    metadata['updated_at'] = self._parse_timestamp(source_metadata[field])
                    break
            
            for field in ['exported_at', 'exported', 'export_time']:
                if field in source_metadata:
                    metadata['exported_at'] = self._parse_timestamp(source_metadata[field])
                    break
            
            # Handle export date/time combination
            if 'export_date' in source_metadata and 'export_time' in source_metadata:
                export_datetime = f"{source_metadata['export_date']} at {source_metadata['export_time']}"
                metadata['exported_at'] = self._parse_timestamp(export_datetime, "%B %d, %Y at %I:%M %p")
            
            # Copy other useful metadata
            if 'tags' in source_metadata:
                metadata['tags'] = source_metadata['tags']
            if 'user' in source_metadata:
                # Could store user info if needed
                pass
        else:
            # Metadata at root level
            metadata['title'] = content.get('title', 'Untitled Conversation')
            
            for field in ['created_at', 'created', 'create_time']:
                if field in content:
                    metadata['created_at'] = self._parse_timestamp(content[field])
                    break
            
            for field in ['updated_at', 'updated', 'update_time']:
                if field in content:
                    metadata['updated_at'] = self._parse_timestamp(content[field])
                    break
        
        # Try to infer platform
        platform = 'unknown'
        content_str = str(content).lower()
        if 'claude' in content_str:
            platform = 'claude-desktop'
        elif 'chatgpt' in content_str or 'gpt' in content_str:
            platform = 'chatgpt'
        elif 'gemini' in content_str:
            platform = 'gemini'
        
        metadata['platform'] = content.get('platform', platform)
        metadata['exporter'] = content.get('exporter', 'claude-exporter-yaml')  # YAML typically from Claude
        
        # Generate chat_id
        metadata['chat_id'] = content.get('id',
                                         content.get('chat_id',
                                                    content.get('conversation_id',
                                                               self._generate_chat_id(metadata['platform']))))
        
        # Parse messages
        messages = []
        source_messages = content.get('messages', [])
        
        for i, msg_data in enumerate(source_messages):
            if isinstance(msg_data, str):
                # Simple string message, assume alternating user/assistant
                role = 'user' if i % 2 == 0 else 'assistant'
                message = {
                    'message_id': f'msg_{i+1:03d}',
                    'role': role,
                    'content': msg_data,
                    'timestamp': None
                }
            else:
                # Dict format
                role = msg_data.get('role', 'user')
                
                # Normalize role
                role_lower = role.lower()
                if role_lower in ['prompt', 'human', 'you']:
                    role = 'user'
                elif role_lower in ['response', 'ai', 'bot', 'claude', 'chatgpt']:
                    role = 'assistant'
                
                message = {
                    'message_id': msg_data.get('id',
                                              msg_data.get('message_id',
                                                          f'msg_{i+1:03d}')),
                    'role': role,
                    'content': msg_data.get('content',
                                           msg_data.get('say',
                                                       msg_data.get('text', ''))),
                    'timestamp': self._parse_timestamp(msg_data.get('timestamp',
                                                                   msg_data.get('created_at',
                                                                              msg_data.get('time'))))
                }
                
                # Handle parent references
                if 'parent' in msg_data or 'parent_message_id' in msg_data:
                    message['parent_message_id'] = msg_data.get('parent_message_id',
                                                               msg_data.get('parent'))
                elif messages:
                    message['parent_message_id'] = messages[-1]['message_id']
                
                # Platform-specific data
                platform_specific = {}
                if 'model' in msg_data:
                    platform_specific['model'] = msg_data['model']
                
                # Handle thinking blocks
                if 'thinking' in msg_data:
                    platform_specific['thinking'] = msg_data['thinking']
                
                if platform_specific:
                    message['platform_specific'] = platform_specific
                
                # Handle attachments
                if 'attachments' in msg_data:
                    message['attachments'] = msg_data['attachments']
            
            messages.append(message)
        
        # Ensure timestamps
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(messages):
            if not msg.get('timestamp'):
                # Simple timestamp generation
                timestamp = now.timestamp() - ((len(messages) - i) * 60)
                msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        
        result['messages'] = messages
        
        # Set metadata defaults
        if messages and not metadata.get('created_at'):
            metadata['created_at'] = messages[0]['timestamp']
        if messages and not metadata.get('updated_at'):
            metadata['updated_at'] = messages[-1]['timestamp']
        
        if not metadata.get('created_at'):
            metadata['created_at'] = datetime.now(timezone.utc).isoformat()
        if not metadata.get('updated_at'):
            metadata['updated_at'] = metadata['created_at']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "YAML Export"


# Register parser
ParserRegistry.register('generic-yaml', GenericYAMLParser)
