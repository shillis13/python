"""
Conversion Framework and Utilities

Core conversion framework and utility functions.
"""

from .conversion_framework import (
    BaseParser,
    ParserRegistry,
    convert_to_v2,
    convert_batch,
    detect_format,
    detect_source,
    load_file,
    validate_v2_schema
)

from .chunker import (
    ChatChunker,
    chunk_chat_file
)

__all__ = [
    'BaseParser',
    'ParserRegistry',
    'convert_to_v2',
    'convert_batch',
    'detect_format',
    'detect_source',
    'load_file',
    'validate_v2_schema',
    'ChatChunker',
    'chunk_chat_file'
]
