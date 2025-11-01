#!/usr/bin/env python3
"""
Basic test to verify chat conversion works
"""
import sys
import subprocess
from pathlib import Path

def test_basic_conversion():
    """Test basic conversion functionality"""
    
    # Test file
    test_file = Path(__file__).parent / "tests/test_cases/chat_converter_test_cases/ChatGPT-Review Pull Requests.json"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"✓ Found test file: {test_file.name}")
    
    # Test 1: Run chat_converter with --help
    print("\n1. Testing chat_converter --help...")
    result = subprocess.run([
        sys.executable, "-m", "chat_processing.chat_converter", "--help"
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0:
        print("✓ chat_converter --help works")
    else:
        print(f"❌ chat_converter --help failed: {result.stderr}")
        return False
    
    # Test 2: Run chat_converter with --list-parsers
    print("\n2. Testing chat_converter --list-parsers...")
    result = subprocess.run([
        sys.executable, "-m", "chat_processing.chat_converter", "--list-parsers"
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0 and "Available Parsers:" in result.stdout:
        print("✓ chat_converter --list-parsers works")
        parsers = [line.strip() for line in result.stdout.split('\n') if line.strip() and not line.startswith('Available') and not line.startswith('-')]
        print(f"  Found {len(parsers)} parsers")
    else:
        print(f"❌ chat_converter --list-parsers failed: {result.stderr}")
        return False
    
    # Test 3: Convert a test file
    print("\n3. Testing actual conversion...")
    output_file = "/tmp/test_output.yaml"
    result = subprocess.run([
        sys.executable, "-m", "chat_processing.chat_converter",
        str(test_file), "-o", output_file
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0:
        print("✓ Conversion completed successfully")
        if Path(output_file).exists():
            print(f"✓ Output file created: {output_file}")
            # Check file size
            size = Path(output_file).stat().st_size
            print(f"  File size: {size:,} bytes")
            return True
        else:
            print(f"❌ Output file not created")
            return False
    else:
        print(f"❌ Conversion failed: {result.stderr}")
        return False

def test_export_splitter():
    """Test chat export splitter"""
    print("\n4. Testing chat_export_splitter --help...")
    
    result = subprocess.run([
        sys.executable, "-m", "chat_processing.chat_export_splitter", "--help"
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0 and "ChatGPT Export Data produces a single .json file" in result.stdout:
        print("✓ chat_export_splitter --help works")
        print("✓ Help text includes the new information about single-line exports")
        return True
    else:
        print(f"❌ chat_export_splitter --help failed: {result.stderr}")
        return False

def main():
    print("=== Chat Processing Basic Tests ===\n")
    
    # Change to ai_utils directory
    import os
    os.chdir(Path(__file__).parent.parent)
    
    all_passed = True
    
    # Run tests
    if not test_basic_conversion():
        all_passed = False
    
    if not test_export_splitter():
        all_passed = False
    
    print("\n=== Summary ===")
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())