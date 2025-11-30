#!/usr/bin/env python3
"""
JSON parser for various chat export formats
Handles native ChatGPT/Claude exports and various exporter JSON formats
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

from chat_processing.lib_converters.conversion_framework import BaseParser, ParserRegistry, validate_v2_schema

logger = logging.getLogger(__name__)


class NativeChatGPTParser(BaseParser):
    """Parser for native ChatGPT JSON exports."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'json' or not isinstance(content, dict):
            return False
        
        # Check for native ChatGPT structure with chat_sessions array
        # Accept either format_version or schema_version at root
        has_sessions = (
            'chat_sessions' in content and
            isinstance(content.get('chat_sessions'), list)
        )
        has_version = 'format_version' in content or 'schema_version' in content
        
        return has_sessions and has_version
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing native ChatGPT JSON format")
        
        # Native ChatGPT exports contain an array of sessions
        # For now, we'll process the first session (or could process all)
        if not content.get('chat_sessions'):
            raise ValueError("No chat sessions found in ChatGPT export")
        
        # Take the first session for now
        # TODO: Handle multiple sessions
        session = content['chat_sessions'][0]
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract metadata
        metadata['chat_id'] = session.get('conversation_id', self._generate_chat_id('chatgpt'))
        metadata['platform'] = 'chatgpt'
        metadata['exporter'] = 'native-chatgpt'
        metadata['title'] = session.get('title', 'ChatGPT Conversation')
        
        # Handle timestamps
        if 'created_at' in session:
            metadata['created_at'] = self._parse_timestamp(session['created_at'])
        if 'updated_at' in session:
            metadata['updated_at'] = self._parse_timestamp(session['updated_at'])
        
        # Extract tags if present
        if 'tags' in session:
            metadata['tags'] = session['tags']
        
        # Parse messages
        messages = []
        for msg_data in session.get('messages', []):
            message = {
                'message_id': msg_data.get('message_id', f'msg_{len(messages)+1:03d}'),
                'role': msg_data.get('role', 'user'),
                'content': msg_data.get('content', ''),
                'timestamp': self._parse_timestamp(msg_data.get('timestamp')),
            }
            
            # Handle parent references if present
            if 'parent_message_id' in msg_data:
                message['parent_message_id'] = msg_data['parent_message_id']
            elif messages:
                # Link to previous message if no explicit parent
                message['parent_message_id'] = messages[-1]['message_id']
            
            # Handle platform-specific data
            platform_specific = {}
            if 'model' in msg_data:
                platform_specific['model'] = msg_data['model']
            if 'metadata' in msg_data:
                platform_specific.update(msg_data['metadata'])
            
            if platform_specific:
                message['platform_specific'] = platform_specific
            
            messages.append(message)
        
        result['messages'] = messages
        
        # Ensure we have timestamps
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
        return "Native ChatGPT Export"


class ChatGPTExporterJSONParser(BaseParser):
    """Parser for ChatGPT Exporter browser extension JSON format."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'json' or not isinstance(content, dict):
            return False
        
        # Check for ChatGPT Exporter patterns
        return any([
            'powered_by' in content and 'ChatGPT Exporter' in str(content.get('powered_by', '')),
            (isinstance(content.get('messages'), list) and 
             any('say' in msg for msg in content.get('messages', []))),
            (isinstance(content.get('messages'), list) and
             any(msg.get('role') == 'Prompt' for msg in content.get('messages', [])))
        ])
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing ChatGPT Exporter JSON format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract metadata
        metadata['title'] = content.get('title', 'ChatGPT Export')
        metadata['platform'] = 'chatgpt'
        metadata['exporter'] = 'ChatGPT Exporter'
        
        # Handle various date formats
        if 'dates' in content:
            dates = content['dates']
            if 'created' in dates:
                metadata['created_at'] = self._parse_timestamp(dates['created'])
            if 'updated' in dates:
                metadata['updated_at'] = self._parse_timestamp(dates['updated'])
            if 'exported' in dates:
                metadata['exported_at'] = self._parse_timestamp(dates['exported'])
        
        # Handle user info if present
        if 'user' in content and isinstance(content['user'], dict):
            # Could store user info in metadata if needed
            pass
        
        # Generate chat_id
        metadata['chat_id'] = self._generate_chat_id('chatgpt', metadata.get('created_at'))
        
        # Parse messages
        messages = []
        for msg_data in content.get('messages', []):
            # Map ChatGPT Exporter format to v2.0
            role = msg_data.get('role', 'user')
            
            # Map Prompt/Response to user/assistant
            if role == 'Prompt':
                role = 'user'
            elif role == 'Response':
                role = 'assistant'
            
            message = {
                'message_id': f'msg_{len(messages)+1:03d}',
                'role': role,
                'content': msg_data.get('say', msg_data.get('content', '')),  # 'say' is used instead of 'content'
                'timestamp': self._parse_timestamp(msg_data.get('timestamp', 
                                                               msg_data.get('date'))),
            }
            
            # Link messages in sequence
            if messages:
                message['parent_message_id'] = messages[-1]['message_id']
            
            # Extract any model info
            if 'model' in msg_data:
                message['platform_specific'] = {'model': msg_data['model']}
            
            messages.append(message)
        
        result['messages'] = messages
        
        # Interpolate timestamps if needed
        if messages and not all(msg.get('timestamp') for msg in messages):
            if metadata.get('created_at') and metadata.get('updated_at'):
                try:
                    start_dt = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(metadata['updated_at'].replace('Z', '+00:00'))
                    
                    time_diff = (end_dt - start_dt).total_seconds()
                    interval = time_diff / max(len(messages) - 1, 1)
                    
                    for i, msg in enumerate(messages):
                        if not msg.get('timestamp'):
                            timestamp = start_dt.timestamp() + (i * interval)
                            msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                except:
                    pass
        
        # Ensure all messages have timestamps
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(messages):
            if not msg.get('timestamp'):
                msg['timestamp'] = now.isoformat()
        
        # Ensure metadata timestamps
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
        return "ChatGPT Exporter JSON"


class SaveMyChatbotJSONParser(BaseParser):
    """Parser for SaveMyChatbot JSON format (Claude exports)."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'json' or not isinstance(content, dict):
            return False
        
        # Check for SaveMyChatbot patterns
        return (
            'metadata' in content and
            isinstance(content.get('metadata'), dict) and
            ('export_date' in content['metadata'] or 'export_time' in content['metadata'])
        )
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing SaveMyChatbot JSON format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        source_metadata = content.get('metadata', {})
        
        # Extract metadata
        metadata['title'] = source_metadata.get('title', content.get('title', 'Claude Chat'))
        metadata['platform'] = 'claude-web'  # SaveMyChatbot is typically for Claude
        metadata['exporter'] = 'SaveMyChatbot'
        
        # Handle export date/time
        export_date = source_metadata.get('export_date', '')
        export_time = source_metadata.get('export_time', '')
        if export_date and export_time:
            # Combine date and time
            export_datetime = f"{export_date} at {export_time}"
            metadata['exported_at'] = self._parse_timestamp(export_datetime, "%B %d, %Y at %I:%M %p")
        elif export_date:
            metadata['exported_at'] = self._parse_timestamp(export_date)
        
        # Generate chat_id
        metadata['chat_id'] = self._generate_chat_id('claude', metadata.get('exported_at'))
        
        # Parse messages
        messages = []
        for msg_data in content.get('messages', []):
            message = {
                'message_id': f'msg_{len(messages)+1:03d}',
                'role': msg_data.get('role', 'user'),
                'content': msg_data.get('content', ''),
                'timestamp': None,  # SaveMyChatbot doesn't include timestamps
            }
            
            # Link messages in sequence
            if messages:
                message['parent_message_id'] = messages[-1]['message_id']
            
            messages.append(message)
        
        # Generate timestamps for messages
        if messages:
            if metadata.get('exported_at'):
                # Work backwards from export time
                try:
                    export_dt = datetime.fromisoformat(metadata['exported_at'].replace('Z', '+00:00'))
                    # Assume 1 minute per message average
                    start_timestamp = export_dt.timestamp() - (len(messages) * 60)
                    
                    for i, msg in enumerate(messages):
                        timestamp = start_timestamp + (i * 60)
                        msg['timestamp'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                except:
                    # Fallback
                    now = datetime.now(timezone.utc)
                    for i, msg in enumerate(messages):
                        msg['timestamp'] = now.isoformat()
            else:
                # Just use current time
                now = datetime.now(timezone.utc)
                for i, msg in enumerate(messages):
                    msg['timestamp'] = now.isoformat()
        
        result['messages'] = messages
        
        # Set timestamps
        if messages:
            metadata['created_at'] = messages[0]['timestamp']
            metadata['updated_at'] = messages[-1]['timestamp']
        else:
            now_iso = datetime.now(timezone.utc).isoformat()
            metadata['created_at'] = now_iso
            metadata['updated_at'] = now_iso
        
        if not metadata.get('exported_at'):
            metadata['exported_at'] = metadata['updated_at']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "SaveMyChatbot JSON"


class ClaudePlatformParser(BaseParser):
    """Parser for Claude platform exports (Settings → Export Data).
    
    Structure:
    - uuid, name, summary, created_at, updated_at
    - account: {uuid}
    - chat_messages[]: sender, text, content[], attachments[], files[]
    """
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format != 'json' or not isinstance(content, dict):
            return False
        
        # Claude platform export has uuid, chat_messages, and sender field in messages
        return all([
            'uuid' in content,
            'chat_messages' in content,
            isinstance(content.get('chat_messages'), list)
        ])
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing Claude platform export format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract metadata
        metadata['chat_id'] = content.get('uuid', self._generate_chat_id('claude'))
        metadata['platform'] = 'claude-web'
        metadata['exporter'] = 'claude-platform-export'
        metadata['title'] = content.get('name') or 'Claude Conversation'
        
        if content.get('summary'):
            metadata['description'] = content['summary']
        
        # Timestamps
        if content.get('created_at'):
            metadata['created_at'] = self._parse_timestamp(content['created_at'])
        if content.get('updated_at'):
            metadata['updated_at'] = self._parse_timestamp(content['updated_at'])
        
        # Process messages
        messages = []
        for i, msg_data in enumerate(content.get('chat_messages', [])):
            # Map sender to role
            sender = msg_data.get('sender', 'unknown').lower()
            if sender == 'human':
                role = 'user'
            elif sender == 'assistant':
                role = 'assistant'
            else:
                role = sender
            
            # Get content - prefer text field, fallback to content blocks
            content_text = msg_data.get('text', '')
            if not content_text and msg_data.get('content'):
                # Join content blocks
                parts = []
                for block in msg_data['content']:
                    if isinstance(block, dict) and block.get('text'):
                        parts.append(block['text'])
                content_text = '\n'.join(parts)
            
            message = {
                'message_id': msg_data.get('uuid', f'msg_{i+1:03d}'),
                'role': role,
                'content': content_text,
                'timestamp': self._parse_timestamp(
                    msg_data.get('created_at') or 
                    msg_data.get('updated_at')
                ),
            }
            
            # Handle attachments/files
            attachments = msg_data.get('attachments', []) + msg_data.get('files', [])
            if attachments:
                message['attachments'] = attachments
            
            # Parent reference
            if messages:
                message['parent_message_id'] = messages[-1]['message_id']
            
            messages.append(message)
        
        result['messages'] = messages
        
        # Ensure metadata timestamps
        if messages and not metadata.get('created_at'):
            metadata['created_at'] = messages[0]['timestamp']
        if messages and not metadata.get('updated_at'):
            metadata['updated_at'] = messages[-1]['timestamp']
        
        metadata['statistics'] = self._compute_statistics(messages)
        
        return result
    
    def get_source_name(self) -> str:
        return "Claude Platform Export"


class V2SchemaParser(BaseParser):
    """Parser for files already in v2.0 schema format.
    
    Validates against schema and passes through unchanged.
    Enables idempotent pipeline processing.
    """
    
    def validate_source(self, content: Any, format: str) -> bool:
        if format not in ('json', 'yaml') or not isinstance(content, dict):
            return False
        return content.get('schema_version') == '2.0'
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        """Validate and pass through v2.0 content unchanged."""
        logger.debug("Processing already-converted v2.0 schema file")
        
        is_valid, error = validate_v2_schema(content)
        if not is_valid:
            raise ValueError(f"Invalid v2.0 schema: {error}")
        
        return content
    
    def get_source_name(self) -> str:
        return "v2-schema"


class GenericJSONParser(BaseParser):
    """Generic JSON parser for various export formats."""
    
    def validate_source(self, content: Any, format: str) -> bool:
        # This is a fallback parser
        if format != 'json' or not isinstance(content, dict):
            return False
        
        # Must have messages array
        return 'messages' in content and isinstance(content['messages'], list)
    
    def parse(self, content: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        logger.debug("Parsing generic JSON format")
        
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        metadata = result['metadata']
        
        # Extract basic metadata
        metadata['title'] = content.get('title', 'Untitled Conversation')
        
        # Try to infer platform
        platform = 'unknown'
        if 'claude' in str(content).lower():
            platform = 'claude-desktop'
        elif 'chatgpt' in str(content).lower() or 'gpt' in str(content).lower():
            platform = 'chatgpt'
        
        metadata['platform'] = content.get('platform', platform)
        metadata['exporter'] = content.get('exporter', 'unknown')
        
        # Handle various timestamp fields
        for field in ['created_at', 'created', 'create_time', 'start_time']:
            if field in content:
                metadata['created_at'] = self._parse_timestamp(content[field])
                break
        
        for field in ['updated_at', 'updated', 'update_time', 'end_time']:
            if field in content:
                metadata['updated_at'] = self._parse_timestamp(content[field])
                break
        
        for field in ['exported_at', 'exported', 'export_time']:
            if field in content:
                metadata['exported_at'] = self._parse_timestamp(content[field])
                break
        
        # Generate chat_id
        metadata['chat_id'] = content.get('id', 
                                         content.get('chat_id',
                                                    content.get('conversation_id',
                                                               self._generate_chat_id(metadata['platform']))))
        
        # Parse messages
        messages = []
        for i, msg_data in enumerate(content.get('messages', [])):
            # Extract role - try various fields
            role = msg_data.get('role')
            if not role:
                role = msg_data.get('author', {}).get('role') if isinstance(msg_data.get('author'), dict) else None
            if not role:
                role = msg_data.get('sender', 'user')
            
            # Normalize role
            role_lower = role.lower() if role else ''
            if role_lower in ['human', 'user', 'you']:
                role = 'user'
            elif role_lower in ['assistant', 'ai', 'bot', 'claude', 'chatgpt', 'gpt']:
                role = 'assistant'
            elif role_lower in ['system']:
                role = 'system'
            elif role_lower in ['tool', 'function']:
                role = 'tool'
            else:
                role = 'user'  # Default
            
            # Extract content - try various fields
            content_text = (msg_data.get('content') or 
                           msg_data.get('text') or 
                           msg_data.get('message') or 
                           msg_data.get('say') or '')
            
            # Handle content as dict
            if isinstance(content_text, dict):
                if 'parts' in content_text:
                    # Join parts
                    content_text = '\n'.join(str(part) for part in content_text['parts'])
                else:
                    content_text = str(content_text)
            
            message = {
                'message_id': msg_data.get('id', 
                                          msg_data.get('message_id', 
                                                      f'msg_{i+1:03d}')),
                'role': role,
                'content': str(content_text),
                'timestamp': self._parse_timestamp(msg_data.get('timestamp',
                                                               msg_data.get('created_at',
                                                                          msg_data.get('time')))),
            }
            
            # Handle parent references
            if 'parent' in msg_data or 'parent_message_id' in msg_data:
                message['parent_message_id'] = msg_data.get('parent_message_id', msg_data.get('parent'))
            elif messages:
                message['parent_message_id'] = messages[-1]['message_id']
            
            # Platform-specific data
            platform_specific = {}
            for key in ['model', 'model_slug', 'engine']:
                if key in msg_data:
                    platform_specific['model'] = msg_data[key]
                    break
            
            # Copy other potentially useful fields
            skip_fields = {'role', 'content', 'text', 'message', 'say', 'timestamp', 
                          'created_at', 'time', 'id', 'message_id', 'parent', 'parent_message_id'}
            for key, value in msg_data.items():
                if key not in skip_fields and isinstance(value, (str, int, float, bool)):
                    platform_specific[key] = value
            
            if platform_specific:
                message['platform_specific'] = platform_specific
            
            messages.append(message)
        
        result['messages'] = messages
        
        # Ensure timestamps on messages
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(messages):
            if not msg.get('timestamp'):
                # Simple timestamp generation
                msg['timestamp'] = now.isoformat()
        
        # Ensure metadata timestamps
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
        return "Generic JSON Export"


# Register parsers
ParserRegistry.register('v2-schema-json', V2SchemaParser)
ParserRegistry.register('claude-platform-json', ClaudePlatformParser)
ParserRegistry.register('native-chatgpt-json', NativeChatGPTParser)
ParserRegistry.register('chatgpt-exporter-json', ChatGPTExporterJSONParser)
ParserRegistry.register('savemychatbot-json', SaveMyChatbotJSONParser)
ParserRegistry.register('generic-json', GenericJSONParser)
