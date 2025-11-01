#!/usr/bin/env python3
"""
Update test files to account for the new directory structure
"""
import os
import re
from pathlib import Path

# Base directory
CHAT_PROC = Path("/Users/shawnhillis/bin/python/src/chat_processing")
TESTS_DIR = CHAT_PROC / "tests"

def update_test_imports(file_path):
    """Update imports in a test file to match new structure"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define import replacements
    replacements = [
        # Update relative imports for parsers
        (r'from chat_processing\.converters\.parsers', 'from chat_processing.lib_parsers'),
        (r'from \.\.converters\.parsers', 'from ..lib_parsers'),
        (r'from \.\.parsers', 'from ..lib_parsers'),
        
        # Update relative imports for formatters
        (r'from chat_processing\.converters\.formatters', 'from chat_processing.lib_formatters'),
        (r'from \.\.converters\.formatters', 'from ..lib_formatters'),
        (r'from \.\.formatters', 'from ..lib_formatters'),
        
        # Update conversion framework imports
        (r'from chat_processing\.converters\.conversion_framework', 'from chat_processing.lib_converters.conversion_framework'),
        (r'from chat_processing\.conversion_framework', 'from chat_processing.lib_converters.conversion_framework'),
        (r'from \.\.conversion_framework', 'from ..lib_converters.conversion_framework'),
        (r'from conversion_framework', 'from lib_converters.conversion_framework'),
        
        # Update convert_chat imports
        (r'from chat_processing\.converters\.convert_chat', 'from chat_processing.chat_converter'),
        (r'from \.\.converters\.convert_chat', 'from ..chat_converter'),
        
        # Update path references in sys.path manipulations
        (r'\.parent\.parent\)', '.parent)'),  # Adjust parent directory references
        (r'src/chat_processing/converters', 'src/chat_processing'),
        
        # Update test case paths
        (r'conversions/export_converter_test_cases', 'chat_processing/tests/chat_converter_test_cases'),
        (r'export_converter_test_cases', 'tests/chat_converter_test_cases'),
    ]
    
    # Apply replacements
    modified = False
    for pattern, replacement in replacements:
        new_content, count = re.subn(pattern, replacement, content)
        if count > 0:
            content = new_content
            modified = True
            print(f"  - Replaced {count} occurrence(s) of '{pattern}'")
    
    # Write back if modified
    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✓ Updated {file_path.name}")
    else:
        print(f"  No changes needed for {file_path.name}")
    
    return modified

def update_all_tests():
    """Update all test files in the tests directory"""
    
    if not TESTS_DIR.exists():
        print(f"Tests directory not found: {TESTS_DIR}")
        return
    
    print(f"Updating test files in {TESTS_DIR}...")
    
    # Find all Python test files
    test_files = list(TESTS_DIR.glob("test_*.py"))
    test_files.extend(TESTS_DIR.glob("*_test.py"))
    
    updated_count = 0
    for test_file in test_files:
        print(f"\nProcessing {test_file.name}...")
        if update_test_imports(test_file):
            updated_count += 1
    
    print(f"\n✓ Updated {updated_count} test file(s)")
    
    # Also update the specific test file we know about
    roundtrip_test = CHAT_PROC / "test_roundtrip_conversions.py"
    if roundtrip_test.exists():
        print(f"\nUpdating {roundtrip_test.name}...")
        update_test_imports(roundtrip_test)

if __name__ == "__main__":
    update_all_tests()
    
    print("\n=== Test update complete! ===")
    print("\nTo verify the tests work:")
    print(f"cd {CHAT_PROC}")
    print("python -m pytest tests/ -v")