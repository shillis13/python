#!/usr/bin/env python3
"""
Extensible Chat Conversion Framework
Handles any export format and transforms to chat_history_v2.0 schema
"""

import json
import yaml
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Abstract base class for all chat parsers."""
    
    @abstractmethod
    def validate_source(self, content: Any, format: str) -> bool:
        """Check if this parser can handle the content."""
        pass
    
    @abstractmethod
    def parse(self, content: Any, file_path: str = None) -> Dict[str, Any]:
        """Convert source format to v2.0 schema."""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this parser's source."""
        pass
    
    def _generate_chat_id(self, platform: str, timestamp: str = None) -> str:
        """Generate a unique chat ID."""
        if not timestamp:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        else:
            # Clean timestamp for use in ID
            timestamp = re.sub(r'[^\d]', '', timestamp)[:14]
        
        return f"{platform}_{timestamp}"
    
    def _parse_timestamp(self, value: Any, format_hint: str = None) -> str:
        """Convert various timestamp formats to ISO 8601."""
        if not value:
            return datetime.now(timezone.utc).isoformat()
            
        if isinstance(value, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        
        if isinstance(value, str):
            # Try common formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%m/%d/%Y at %I:%M %p",
                "%B %d, %Y at %I:%M %p",
            ]
            
            if format_hint:
                formats.insert(0, format_hint)
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(value.strip(), fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
                except ValueError:
                    continue
        
        # If already valid ISO format, return as-is
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return value
        except:
            pass
            
        # Fallback to current time
        logger.warning(f"Could not parse timestamp: {value}")
        return datetime.now(timezone.utc).isoformat()
    
    def _compute_statistics(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate conversation statistics."""
        if not messages:
            return {
                'message_count': 0,
                'word_count': 0,
                'token_count': 0,
                'duration_seconds': 0
            }
        
        word_count = sum(len(msg.get('content', '').split()) for msg in messages)
        message_count = len(messages)
        
        # Rough token estimation (words * 1.3)
        token_count = int(word_count * 1.3)
        
        # Calculate duration
        duration = 0
        if len(messages) >= 2:
            try:
                first_ts = self._parse_timestamp(messages[0].get('timestamp'))
                last_ts = self._parse_timestamp(messages[-1].get('timestamp'))
                
                first_dt = datetime.fromisoformat(first_ts.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
                
                duration = (last_dt - first_dt).total_seconds()
            except Exception as e:
                logger.debug(f"Could not calculate duration: {e}")
                duration = 0
        
        return {
            'message_count': message_count,
            'word_count': word_count,
            'token_count': token_count,
            'duration_seconds': max(0, duration)
        }


class ParserRegistry:
    """Registry for parser implementations."""
    
    _parsers: Dict[str, Type[BaseParser]] = {}
    
    @classmethod
    def register(cls, name: str, parser_class: Type[BaseParser]) -> None:
        """Register a parser implementation."""
        cls._parsers[name] = parser_class
        logger.info(f"Registered parser: {name}")
    
    @classmethod
    def get_parser(cls, content: Any, format: str) -> Optional[BaseParser]:
        """Get the appropriate parser for the content."""
        for name, parser_class in cls._parsers.items():
            parser = parser_class()
            try:
                if parser.validate_source(content, format):
                    logger.info(f"Selected parser: {name}")
                    return parser
            except Exception as e:
                logger.debug(f"Parser {name} validation error: {e}")
                continue
        
        logger.warning(f"No parser found for format: {format}")
        return None
    
    @classmethod
    def list_parsers(cls) -> List[str]:
        """List all registered parsers."""
        return list(cls._parsers.keys())


def detect_format(file_path: str) -> str:
    """
    Auto-detect file format based on extension and content inspection.
    Returns: 'markdown', 'json', 'yaml', 'html', or 'unknown'
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    
    # First try by extension
    extension_map = {
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.html': 'html',
        '.htm': 'html'
    }
    
    format = extension_map.get(ext, 'unknown')
    
    # If unknown or ambiguous, inspect content
    if format in ['unknown'] or not path.exists():
        return format
    
    try:
        # Read first 1KB for inspection
        with open(file_path, 'r', encoding='utf-8') as f:
            sample = f.read(1024)
        
        # Check for format indicators
        if format == 'unknown':
            if sample.strip().startswith('{') or sample.strip().startswith('['):
                format = 'json'
            elif sample.strip().startswith('---') or ':' in sample.split('\n')[0]:
                format = 'yaml'
            elif sample.strip().startswith('<!DOCTYPE') or sample.strip().startswith('<html'):
                format = 'html'
            elif re.search(r'^#{1,6}\s+', sample, re.MULTILINE):
                format = 'markdown'
            elif re.search(r'\*\*User:\*\*|\*\*Assistant:\*\*', sample):
                format = 'markdown'
        
        # Verify format matches content
        elif format == 'json':
            # Verify it's actually JSON
            try:
                json.loads(sample)
            except:
                # Might be malformed, check if it looks like JSON
                if not (sample.strip().startswith('{') or sample.strip().startswith('[')):
                    format = 'unknown'
        
    except Exception as e:
        logger.debug(f"Error inspecting file content: {e}")
    
    logger.info(f"Detected format for {file_path}: {format}")
    return format


def load_file(file_path: str, format: str) -> Any:
    """Load file content based on format."""
    try:
        if format == 'json':
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        elif format == 'yaml':
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        elif format in ['markdown', 'html', 'unknown']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        raise


def detect_source(content: Any, format: str) -> str:
    """
    Identify export tool after parsing.
    Returns: 'claude-exporter', 'chatgpt-exporter', 'native-chatgpt', etc.
    """
    source = 'unknown'
    
    try:
        if format == 'json':
            if isinstance(content, dict):
                # Check for specific patterns
                if 'chat_sessions' in content and 'format_version' in content:
                    source = 'native-chatgpt'
                elif 'powered_by' in content and 'ChatGPT Exporter' in str(content.get('powered_by', '')):
                    source = 'chatgpt-exporter'
                elif 'metadata' in content and 'export_date' in content.get('metadata', {}):
                    source = 'claude-savemychatbot'
                elif 'messages' in content and any('say' in msg for msg in content.get('messages', [])):
                    source = 'chatgpt-exporter'
                elif 'title' in content and 'messages' in content:
                    # Could be various exporters
                    messages = content.get('messages', [])
                    if messages and 'role' in messages[0]:
                        roles = [msg.get('role', '') for msg in messages]
                        if 'Prompt' in roles:
                            source = 'chatgpt-exporter'
                        else:
                            source = 'generic-exporter'
        
        elif format == 'markdown':
            if isinstance(content, str):
                # Check markdown patterns
                if 'SaveMyChatbot' in content or 'export date:' in content.lower():
                    source = 'claude-savemychatbot'
                elif '## Prompt:' in content or '## Response:' in content:
                    source = 'chatgpt-exporter-md'
                elif '## User' in content or '## Assistant' in content:
                    source = 'claude-exporter-md'
                elif '**You:**' in content or '**ChatGPT:**' in content:
                    source = 'generic-chatgpt-md'
                elif '**User:**' in content or '**Claude:**' in content:
                    source = 'generic-claude-md'
        
        elif format == 'yaml':
            if isinstance(content, dict):
                # YAML exports are typically from Claude exporters
                if 'metadata' in content or 'messages' in content:
                    source = 'claude-exporter-yaml'
        
        elif format == 'html':
            if isinstance(content, str):
                # HTML exports need content inspection
                if 'Claude Chat' in content:
                    source = 'claude-exporter-html'
                elif 'ChatGPT' in content:
                    source = 'chatgpt-exporter-html'
    
    except Exception as e:
        logger.debug(f"Error detecting source: {e}")
    
    logger.info(f"Detected source: {source}")
    return source


def validate_v2_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate data against v2.0 schema.
    Returns: (is_valid, error_message)
    """
    # Import jsonschema if available
    try:
        from jsonschema import validate, ValidationError
        
        # Load schema
        schema_path = Path(__file__).parent.parent / 'schemas' / 'chat_history_v2.0.schema.json'
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            try:
                validate(instance=data, schema=schema)
                return True, None
            except ValidationError as e:
                error_path = ' -> '.join(str(p) for p in e.path) if e.path else 'root'
                return False, f"Validation error at {error_path}: {e.message}"
        else:
            logger.warning("Schema file not found, skipping validation")
            return True, None
            
    except ImportError:
        logger.warning("jsonschema not installed, skipping validation")
        return True, None
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def convert_to_v2(file_path: str, validate: bool = True) -> Dict[str, Any]:
    """
    Main conversion pipeline.
    Orchestrate detection → parsing → validation.
    """
    logger.info(f"Converting file: {file_path}")
    
    # Detect format
    format = detect_format(file_path)
    if format == 'unknown':
        raise ValueError(f"Could not detect format for: {file_path}")
    
    # Load file
    content = load_file(file_path, format)
    
    # Detect source
    source = detect_source(content, format)
    
    # Get appropriate parser
    parser = ParserRegistry.get_parser(content, format)
    if not parser:
        raise ValueError(f"No parser available for source: {source}, format: {format}")
    
    # Parse to v2.0 format
    v2_data = parser.parse(content, file_path)
    
    # Validate if requested
    if validate:
        is_valid, error = validate_v2_schema(v2_data)
        if not is_valid:
            logger.warning(f"Validation failed: {error}")
            # Don't fail completely, allow partial conversions
    
    logger.info(f"Conversion complete for: {file_path}")
    return v2_data


def convert_batch(file_paths: List[str], output_dir: str = None, validate: bool = True) -> Dict[str, Any]:
    """
    Convert multiple files in batch.
    Returns results dictionary with successes and failures.
    """
    results = {
        'successful': [],
        'failed': [],
        'total': len(file_paths)
    }
    
    for file_path in file_paths:
        try:
            # Convert file
            v2_data = convert_to_v2(file_path, validate)
            
            # Determine output path
            if output_dir:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                output_name = Path(file_path).stem + '_v2.json'
                output_path = os.path.join(output_dir, output_name)
            else:
                output_path = str(Path(file_path).with_suffix('.v2.json'))
            
            # Save converted data
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(v2_data, f, indent=2, ensure_ascii=False)
            
            results['successful'].append({
                'input': file_path,
                'output': output_path,
                'chat_id': v2_data['metadata']['chat_id']
            })
            
        except Exception as e:
            logger.error(f"Failed to convert {file_path}: {e}")
            results['failed'].append({
                'input': file_path,
                'error': str(e)
            })
    
    return results