#!/usr/bin/env python3
"""Test suite for chat processing tools after renaming/reorganization"""
import json
import tempfile
import subprocess
import sys
from pathlib import Path
import shutil

def create_test_data():
    """Create various test data formats"""
    
    # Test data 1: Simple array of chats
    array_data = [
        {
            "conversation_id": "chat_001",
            "title": "First Chat",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        },
        {
            "conversation_id": "chat_002", 
            "title": "Second Chat",
            "messages": [
                {"role": "user", "content": "How are you?"},
                {"role": "assistant", "content": "I'm doing well!"}
            ]
        }
    ]
    
    # Test data 2: Wrapped format
    wrapped_data = {
        "conversations": [
            {
                "id": "chat_003",
                "title": "Wrapped Chat 1",
                "messages": []
            },
            {
                "id": "chat_004",
                "title": "Wrapped Chat 2", 
                "messages": []
            }
        ]
    }
    
    # Test data 3: Single conversation with mapping
    single_mapping = {
        "conversation_id": "chat_005",
        "title": "Complex Single Chat",
        "mapping": {
            "msg1": {"message": {"role": "user", "content": "Test"}},
            "msg2": {"message": {"role": "assistant", "content": "Response"}}
        }
    }
    
    return {
        "array": array_data,
        "wrapped": wrapped_data,
        "single": single_mapping
    }

def test_chats_splitter():
    """Test the chats_splitter.py functionality"""
    print("=== Testing chats_splitter.py ===\n")
    
    test_data = create_test_data()
    results = []
    
    # Create temp directory for outputs
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test each format
        for format_name, data in test_data.items():
            print(f"Testing {format_name} format...")
            
            # Create input file
            input_file = temp_path / f"test_{format_name}.json"
            with open(input_file, 'w') as f:
                json.dump(data, f)
            
            # Create output directory
            output_dir = temp_path / f"output_{format_name}"
            
            # Run chats_splitter
            result = subprocess.run([
                sys.executable, "-m", "chat_processing.chats_splitter",
                str(input_file), "-o", str(output_dir)
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode == 0:
                # Count output files
                output_files = list(output_dir.glob("*.json"))
                expected = len(data) if isinstance(data, list) else (
                    len(data.get("conversations", [])) if "conversations" in data else 1
                )
                
                if len(output_files) == expected:
                    print(f"  ✓ Created {len(output_files)} files (expected {expected})")
                    results.append(True)
                else:
                    print(f"  ✗ Created {len(output_files)} files (expected {expected})")
                    results.append(False)
            else:
                print(f"  ✗ Failed: {result.stderr}")
                results.append(False)
    
    return all(results)

def test_chat_converter():
    """Test the chat_converter.py functionality"""
    print("\n=== Testing chat_converter.py ===\n")
    
    # Use existing test file
    test_file = Path(__file__).parent / "tests/test_cases/chat_converter_test_cases/ChatGPT-Review Pull Requests.json"
    
    if not test_file.exists():
        print("✗ Test file not found")
        return False
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test different output formats
        formats = ['json', 'yaml', 'md', 'html']
        results = []
        
        for fmt in formats:
            print(f"Testing conversion to {fmt}...")
            output_file = temp_path / f"output.{fmt}"
            
            result = subprocess.run([
                sys.executable, "-m", "chat_processing.chat_converter",
                str(test_file), "-o", str(output_file)
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode == 0 and output_file.exists():
                size = output_file.stat().st_size
                print(f"  ✓ Created {fmt} file ({size:,} bytes)")
                results.append(True)
            else:
                print(f"  ✗ Failed to create {fmt} file")
                if result.stderr:
                    print(f"    Error: {result.stderr}")
                results.append(False)
    
    return all(results)

def test_integration():
    """Test the integration: split then convert"""
    print("\n=== Testing Integration: Split → Convert ===\n")
    
    # Create test data with multiple chats
    test_data = [
        {
            "conversation_id": "test_001",
            "title": "Integration Test 1",
            "messages": [{"role": "user", "content": "Test 1"}]
        },
        {
            "conversation_id": "test_002",
            "title": "Integration Test 2", 
            "messages": [{"role": "user", "content": "Test 2"}]
        }
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Create multi-chat file
        input_file = temp_path / "multi_chat.json"
        with open(input_file, 'w') as f:
            json.dump(test_data, f)
        
        # Step 2: Split into individual files
        split_dir = temp_path / "split"
        print("1. Splitting multi-chat file...")
        
        result = subprocess.run([
            sys.executable, "-m", "chat_processing.chats_splitter",
            str(input_file), "-o", str(split_dir)
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode != 0:
            print(f"  ✗ Split failed: {result.stderr}")
            return False
        
        split_files = list(split_dir.glob("*.json"))
        print(f"  ✓ Split into {len(split_files)} files")
        
        # Step 3: Convert one of the split files
        if split_files:
            print("\n2. Converting first split file to YAML...")
            first_file = split_files[0]
            output_file = temp_path / "converted.yaml"
            
            result = subprocess.run([
                sys.executable, "-m", "chat_processing.chat_converter",
                str(first_file), "-o", str(output_file)
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode == 0 and output_file.exists():
                print(f"  ✓ Converted to YAML successfully")
                return True
            else:
                print(f"  ✗ Conversion failed")
                return False
    
    return False

def test_help_commands():
    """Test that help commands work"""
    print("\n=== Testing Help Commands ===\n")
    
    tools = ["chats_splitter", "chat_converter"]
    results = []
    
    for tool in tools:
        result = subprocess.run([
            sys.executable, "-m", f"chat_processing.{tool}", "--help"
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode == 0:
            print(f"✓ {tool} --help works")
            results.append(True)
        else:
            print(f"✗ {tool} --help failed")
            results.append(False)
    
    return all(results)

def main():
    print("Chat Processing Tools Test Suite")
    print("=" * 50)
    print()
    
    # Change to ai_utils directory
    import os
    os.chdir(Path(__file__).parent.parent)
    
    tests = [
        ("Help Commands", test_help_commands),
        ("Chats Splitter", test_chats_splitter),
        ("Chat Converter", test_chat_converter),
        ("Integration", test_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print("=" * 50)
    
    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    if all(results):
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())