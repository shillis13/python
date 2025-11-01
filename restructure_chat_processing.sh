#!/bin/bash
# Script to restructure chat_processing directory

# Base directories
SRC_DIR="/Users/shawnhillis/bin/python/src"
CHAT_PROC="$SRC_DIR/chat_processing"
CONVERSIONS="$SRC_DIR/conversions"

echo "=== Restructuring chat_processing directory ==="

# 1. Move the main converter script to top level and rename
echo "1. Moving convert_chat.py to top level as chat_converter.py..."
mv "$CHAT_PROC/converters/convert_chat.py" "$CHAT_PROC/chat_converter.py" 2>/dev/null || echo "  Already moved"

# 2. Move parsers and formatters to top level
echo "2. Moving parsers and formatters to top level..."
if [ -d "$CHAT_PROC/converters/parsers" ]; then
    mv "$CHAT_PROC/converters/parsers" "$CHAT_PROC/parsers"
fi
if [ -d "$CHAT_PROC/converters/formatters" ]; then
    mv "$CHAT_PROC/converters/formatters" "$CHAT_PROC/formatters"
fi

# 3. Move conversion_framework.py to top level
echo "3. Moving conversion_framework.py..."
if [ -f "$CHAT_PROC/converters/conversion_framework.py" ]; then
    mv "$CHAT_PROC/converters/conversion_framework.py" "$CHAT_PROC/conversion_framework.py"
fi

# 4. Copy doc_converter from conversions
echo "4. Copying doc_converter.py..."
if [ -f "$CONVERSIONS/doc_converter.py" ]; then
    cp "$CONVERSIONS/doc_converter.py" "$CHAT_PROC/doc_converter.py"
    # Also copy its library
    cp "$CONVERSIONS/lib_doc_converter.py" "$CHAT_PROC/lib_doc_converter.py" 2>/dev/null
    cp "$CONVERSIONS/conversion_utils.py" "$CHAT_PROC/conversion_utils.py" 2>/dev/null
fi

# 5. Rename split_conversations.py to chat_chunker.py
echo "5. Renaming split_conversations.py to chat_chunker.py..."
if [ -f "$CHAT_PROC/split_conversations.py" ]; then
    mv "$CHAT_PROC/split_conversations.py" "$CHAT_PROC/chat_chunker.py"
fi

# 6. Create test_cases directory structure
echo "6. Creating test_cases directory structure..."
mkdir -p "$CHAT_PROC/test_cases/chat_converter_test_cases"
mkdir -p "$CHAT_PROC/test_cases/chat_export_splitter_test_cases"
mkdir -p "$CHAT_PROC/test_cases/chat_chunker_test_cases"

# 7. Move existing test cases
echo "7. Moving existing test cases..."
if [ -d "$CONVERSIONS/export_converter_test_cases" ]; then
    cp -r "$CONVERSIONS/export_converter_test_cases"/* "$CHAT_PROC/test_cases/chat_converter_test_cases/" 2>/dev/null
fi

# 8. Move test files
if [ -d "$CHAT_PROC/tests" ]; then
    cp -r "$CHAT_PROC/tests"/* "$CHAT_PROC/test_cases/" 2>/dev/null
fi

# 9. Update imports in moved files
echo "8. Updating imports..."

# Update chat_converter.py imports
if [ -f "$CHAT_PROC/chat_converter.py" ]; then
    sed -i.bak 's/from chat_processing\.converters\.conversion_framework/from conversion_framework/g' "$CHAT_PROC/chat_converter.py"
    sed -i.bak 's/from chat_processing\.converters\.parsers/from parsers/g' "$CHAT_PROC/chat_converter.py"
    sed -i.bak 's/from chat_processing\.converters\.formatters/from formatters/g' "$CHAT_PROC/chat_converter.py"
    rm "$CHAT_PROC/chat_converter.py.bak"
fi

# 10. Clean up empty converters directory
echo "9. Cleaning up..."
if [ -d "$CHAT_PROC/converters" ]; then
    rmdir "$CHAT_PROC/converters" 2>/dev/null || echo "  Converters dir not empty"
fi

# 11. Update __init__.py files
echo "10. Updating __init__.py files..."
echo "# Chat Processing Package" > "$CHAT_PROC/__init__.py"
echo "# Parsers Package" > "$CHAT_PROC/parsers/__init__.py" 2>/dev/null
echo "# Formatters Package" > "$CHAT_PROC/formatters/__init__.py" 2>/dev/null

echo ""
echo "=== Directory structure after restructuring ==="
tree -L 2 "$CHAT_PROC" 2>/dev/null || ls -la "$CHAT_PROC"

echo ""
echo "=== Next steps ==="
echo "1. Delete ai_utils/chat_conversions/: rm -rf $SRC_DIR/ai_utils/chat_conversions"
echo "2. Delete conversions/: rm -rf $CONVERSIONS"
echo "3. Move chat_processing to ai_utils: mv $CHAT_PROC $SRC_DIR/ai_utils/"
echo "4. Create symlinks in ~/bin/python/scripts for executables"
echo ""
echo "To create symlinks:"
echo "  ln -s $SRC_DIR/ai_utils/chat_processing/chat_converter.py ~/bin/python/scripts/chat_converter"
echo "  ln -s $SRC_DIR/ai_utils/chat_processing/chat_export_splitter.py ~/bin/python/scripts/chat_export_splitter"
echo "  ln -s $SRC_DIR/ai_utils/chat_processing/chat_chunker.py ~/bin/python/scripts/chat_chunker"
echo "  ln -s $SRC_DIR/ai_utils/chat_processing/doc_converter.py ~/bin/python/scripts/doc_converter"