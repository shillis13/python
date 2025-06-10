#!/usr/bin/env python3

import os
import shutil
import subprocess
import pytest

#from lib_logging import parse_log_level_args

# Parse the log level from the command line arguments
#parse_log_level_args()

# Directory where test files will be created
TEST_DIR = "test_files_renameFiles"

# Helper function to create test files
def create_test_files(files):
    os.makedirs(TEST_DIR, exist_ok=True)
    for file in files:
        open(os.path.join(TEST_DIR, file), 'w').close()

# Helper function to remove test files and directory
def cleanup_test_files():
    if os.path.exists(TEST_DIR):
        #shutil.rmtree(TEST_DIR)
        return

# Helper function to run the renameFiles.py script
def run_rename_command(args, execute=True):
    command = ["python3", "renameFiles.py"] + args

    if execute:
        command.append("--exec")

    result = subprocess.run(command, cwd=TEST_DIR, capture_output=True, text=True)
    return result

# Basic Rename Operation
def test_basic_rename():
    create_test_files(['file_old.txt', 'old_file.txt'])
    run_rename_command(["--find", "old", "--replace", "new"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "file_new.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "new_file.txt"))
    
    cleanup_test_files()

# Using Format
def test_using_format():
    create_test_files(['file.txt', 'report.docx'])
    run_rename_command(["--format", "{date}-{name}.{ext}"])
    
    today = "2024-08-30"  # Replace with current date dynamically if needed
    assert os.path.exists(os.path.join(TEST_DIR, f"{today}-file.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, f"{today}-report.docx"))
    
    cleanup_test_files()

# Remove Vowels
def test_remove_vowels():
    create_test_files(['hello.txt', 'world.txt'])
    run_rename_command(["--remove-vowels"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "hll.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "wrld.txt"))
    
    cleanup_test_files()

# Change Case to Lowercase
def test_change_case_lower():
    create_test_files(['MyFile.TXT', 'AnotherFile.DOCX'])
    run_rename_command(["--change-case", "lower"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "myfile.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "anotherfile.docx"))
    
    cleanup_test_files()

# Replace Whitespace with Underscores
def test_replace_whitespace():
    create_test_files(['my file.txt', 'another file.docx'])
    run_rename_command(["--replace-white-space", "_"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "my_file.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "another_file.docx"))
    
    cleanup_test_files()

# Sequential Numbering
def test_sequential_numbering():
    create_test_files(['img_1.jpg', 'img_2.jpg'])
    run_rename_command(["--format", "image-{%03d}.{ext}"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "image-001.jpg"))
    assert os.path.exists(os.path.join(TEST_DIR, "image-002.jpg"))
    
    cleanup_test_files()

# Handling Special Characters
def test_handle_special_chars():
    create_test_files(['file@name$.txt', '#weird&file!.doc'])
    run_rename_command(["--no-clean"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "filename.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "weirdfile.doc"))
    
    cleanup_test_files()

# Leading and Trailing Whitespace
def test_leading_trailing_whitespace():
    create_test_files(['  file.txt  ', '  report.doc  '])
    run_rename_command(["--no-clean"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "file.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "report.doc"))
    
    cleanup_test_files()

# Combine Multiple Options
def test_combine_options():
    create_test_files(['IMG_1234.JPG', 'IMG_5678.JPG'])
    run_rename_command(["--find", "IMG", "--replace", "Photo", "--change-case", "lower", "--remove-vowels"])
    
    assert os.path.exists(os.path.join(TEST_DIR, "ph_1234.jpg"))
    assert os.path.exists(os.path.join(TEST_DIR, "ph_5678.jpg"))
    
    cleanup_test_files()

# Dry Run
def test_dry_run():
    create_test_files(['file_old.txt', 'old_file.txt'])
    result = run_rename_command(["--find", "old", "--replace", "new", "--dry-run"])
    
    # Check that files were not renamed
    assert os.path.exists(os.path.join(TEST_DIR, "file_old.txt"))
    assert os.path.exists(os.path.join(TEST_DIR, "old_file.txt"))
    
    # Check dry-run output
    assert "file_old.txt" in result.stdout
    assert "file_new.txt" in result.stdout
    assert "old_file.txt" in result.stdout
    assert "new_file.txt" in result.stdout
    
    cleanup_test_files()

# Undo Last Operation
def test_undo_operation():
    create_test_files(['file_old.txt'])
    run_rename_command(["--find", "old", "--replace", "new"])
    
    # Undo the rename operation
    run_rename_command(["--undo"])
    
    # Check that files were reverted
    assert os.path.exists(os.path.join(TEST_DIR, "file_old.txt"))
    assert not os.path.exists(os.path.join(TEST_DIR, "file_new.txt"))
    
    cleanup_test_files()

# Display Help
def test_display_help():
    result = run_rename_command(["--help-verbose"])
    
    assert "Detailed Help with Examples" in result.stdout

# Display Usage
def test_display_usage():
    result = run_rename_command(["--usage"])
    
    assert "Usage: renameFiles.py [options]" in result.stdout

# Invalid Command
def test_invalid_command():
    result = run_rename_command(["--invalid-command"])
    
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr


if __name__ == "__main__":
    pytest.main()

