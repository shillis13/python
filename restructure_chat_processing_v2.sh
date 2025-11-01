#!/bin/bash
# Script to restructure chat_processing directory with lib_ prefix convention

# Base directory
CHAT_PROC="/Users/shawnhillis/bin/python/src/chat_processing"

echo "=== Restructuring chat_processing directory (v2) ==="

# 1. Rename parsers to lib_parsers
echo "1. Renaming parsers to lib_parsers..."
if [ -d "$CHAT_PROC/parsers" ]; then
    mv "$CHAT_PROC/parsers" "$CHAT_PROC/lib_parsers"
fi

# 2. Rename formatters to lib_formatters
echo "2. Renaming formatters to lib_formatters..."
if [ -d "$CHAT_PROC/formatters" ]; then
    mv "$CHAT_PROC/formatters" "$CHAT_PROC/lib_formatters"
fi

# 3. Create lib_converters directory
echo "3. Creating lib_converters directory..."
mkdir -p "$CHAT_PROC/lib_converters"

# 4. Move lib_doc_converter.py to lib_converters
echo "4. Moving lib_doc_converter.py to lib_converters..."
if [ -f "$CHAT_PROC/lib_doc_converter.py" ]; then
    mv "$CHAT_PROC/lib_doc_converter.py" "$CHAT_PROC/lib_converters/"
fi

# 5. Rename and move conversion_utils.py
echo "5. Moving conversion_utils.py to lib_converters/lib_conversion_utils.py..."
if [ -f "$CHAT_PROC/conversion_utils.py" ]; then
    mv "$CHAT_PROC/conversion_utils.py" "$CHAT_PROC/lib_converters/lib_conversion_utils.py"
fi

# 6. Move conversion_framework.py to lib_converters
echo "6. Moving conversion_framework.py to lib_converters..."
if [ -f "$CHAT_PROC/conversion_framework.py" ]; then
    mv "$CHAT_PROC/conversion_framework.py" "$CHAT_PROC/lib_converters/conversion_framework.py"
fi

# 7-9 are already done per FYI notes

# 10. Create/Update __init__.py files
echo "10. Creating __init__.py files..."

# Main __init__.py
cat > "$CHAT_PROC/__init__.py" << 'EOF'
"""
Chat Processing Package

This package provides tools for converting chat histories between various formats.
"""

__version__ = "2.0.0"
EOF

# lib_parsers __init__.py
cat > "$CHAT_PROC/lib_parsers/__init__.py" << 'EOF'
"""
Chat Format Parsers

This module contains parsers for various chat export formats.
Each parser converts its specific format to the standard v2.0 schema.
"""

# Import all parsers to register them
from . import json_parser
from . import markdown_parser
from . import yaml_parser
from . import html_parser

__all__ = ['json_parser', 'markdown_parser', 'yaml_parser', 'html_parser']
EOF

# lib_formatters __init__.py
cat > "$CHAT_PROC/lib_formatters/__init__.py" << 'EOF'
"""
Chat Format Formatters

This module contains formatters that convert v2.0 schema data
to various output formats.
"""

from .markdown_formatter import format_as_markdown
from .html_formatter import format_as_html

__all__ = ['format_as_markdown', 'format_as_html']
EOF

# lib_converters __init__.py
cat > "$CHAT_PROC/lib_converters/__init__.py" << 'EOF'
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

__all__ = [
    'BaseParser',
    'ParserRegistry', 
    'convert_to_v2',
    'convert_batch',
    'detect_format',
    'detect_source',
    'load_file',
    'validate_v2_schema'
]
EOF

echo "=== Updating import statements in all Python files ==="

# Function to update imports in a file
update_imports() {
    local file=$1
    if [ -f "$file" ]; then
        # Update parser imports
        sed -i.bak 's/from parsers/from lib_parsers/g' "$file"
        sed -i.bak 's/from \.parsers/from .lib_parsers/g' "$file"
        sed -i.bak 's/from chat_processing\.parsers/from chat_processing.lib_parsers/g' "$file"
        sed -i.bak 's/import parsers/import lib_parsers/g' "$file"
        
        # Update formatter imports
        sed -i.bak 's/from formatters/from lib_formatters/g' "$file"
        sed -i.bak 's/from \.formatters/from .lib_formatters/g' "$file"
        sed -i.bak 's/from chat_processing\.formatters/from chat_processing.lib_formatters/g' "$file"
        sed -i.bak 's/import formatters/import lib_formatters/g' "$file"
        
        # Update conversion framework imports
        sed -i.bak 's/from conversion_framework/from lib_converters.conversion_framework/g' "$file"
        sed -i.bak 's/from \.conversion_framework/from ..lib_converters.conversion_framework/g' "$file"
        sed -i.bak 's/from \.\.conversion_framework/from ..lib_converters.conversion_framework/g' "$file"
        sed -i.bak 's/import conversion_framework/import lib_converters.conversion_framework/g' "$file"
        
        # Update conversion_utils imports
        sed -i.bak 's/import conversion_utils/import lib_converters.lib_conversion_utils/g' "$file"
        sed -i.bak 's/from conversion_utils/from lib_converters.lib_conversion_utils/g' "$file"
        
        # Update lib_doc_converter imports
        sed -i.bak 's/import lib_doc_converter/import lib_converters.lib_doc_converter/g' "$file"
        sed -i.bak 's/from lib_doc_converter/from lib_converters.lib_doc_converter/g' "$file"
        
        # Clean up backup files
        rm -f "${file}.bak"
    fi
}

# Update imports in all Python files
echo "Updating imports in chat_converter.py..."
update_imports "$CHAT_PROC/chat_converter.py"

echo "Updating imports in doc_converter.py..."
update_imports "$CHAT_PROC/doc_converter.py"

echo "Updating imports in chat_export_splitter.py..."
update_imports "$CHAT_PROC/chat_export_splitter.py"

echo "Updating imports in chat_chunker.py..."
update_imports "$CHAT_PROC/chat_chunker.py"

# Update imports in all parser files
for file in "$CHAT_PROC/lib_parsers"/*.py; do
    echo "Updating imports in $(basename $file)..."
    update_imports "$file"
done

# Update imports in all formatter files
for file in "$CHAT_PROC/lib_formatters"/*.py; do
    echo "Updating imports in $(basename $file)..."
    update_imports "$file"
done

# Update imports in lib_converters
for file in "$CHAT_PROC/lib_converters"/*.py; do
    echo "Updating imports in $(basename $file)..."
    update_imports "$file"
done

# Update imports in test files
if [ -d "$CHAT_PROC/tests" ]; then
    for file in "$CHAT_PROC/tests"/*.py; do
        if [ -f "$file" ]; then
            echo "Updating imports in test: $(basename $file)..."
            update_imports "$file"
        fi
    done
fi

echo ""
echo "=== Directory structure after restructuring ==="
tree -L 2 "$CHAT_PROC" 2>/dev/null || find "$CHAT_PROC" -type f -name "*.py" | sort

echo ""
echo "=== Restructuring complete! ==="
echo ""
echo "Next steps:"
echo "1. Test the imports: cd $CHAT_PROC && python -m chat_converter --help"
echo "2. Run tests: cd $CHAT_PROC && python -m pytest tests/"
echo "3. Create symlinks in ~/bin/python/scripts for the executable scripts"