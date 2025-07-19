# Design and Feature Proposal: archive_util

This document outlines a revised design for a new Python-based archive utility. The goal is to create a single, powerful tool for creating and extracting zip (with AES encryption) and tar archives, integrating seamlessly with the existing project structure.

## 1. Revised Feature SetThe utility will be focused on zip and tar formats, with capabilities for both creation and extraction.

### Core Features
* Archive Creation:Create .zip archives with optional AES-256 password protection.Create .tar archives (e.g., .tar, .tar.gz, .tar.bz2). The specific tar compression will be inferred from the output filename.
* Archive Extraction:Extract files from .zip archives, handling password-protected (AES) and unencrypted files.Extract files from all common .tar formats.
* Relative Path Storage (Default): By default, store files in archives using relative paths to ensure portability. An option to use absolute paths will be available.Cross-Platform Compatibility: Ensure archives created on macOS are fully readable and extractable by standard tools on Windows and Linux.
* Advanced Features (Retained from previous proposal)Powerful File Filtering: Integrate directly with file_utils/fsFilters.py and file_utils/lib_fileinput.py for sophisticated inclusion/exclusion rules during archive creation.Update/Freshen Modes (for Zip): Support for updating and freshening existing .zip archives. (Note: This is more complex for .tar files and would be a lower priority).
* Archive Management:List Contents: A command to list the contents of both zip and tar archives without extracting.Test Integrity: A command to verify the integrity of archives.

## 2. Revised Design & ArchitectureThe utility will be built as a single, format-aware tool to provide a consistent user experience.

### Directory Structure
We will create a new package directory: 

src/archive_utils/.src/
├── file_utils/
└── archive_utils/
    ├── __init__.py
    ├── lib_archive.py      # Core library with format-aware logic
    └── cli_archive.py      # Unified command-line interface

### Core Library: lib_archive.py
This library will contain the core logic for handling different archive formats. It will use a factory pattern or strategy pattern to delegate operations to the correct backend (pyzipper for zip, tarfile for tar).Technology Choices:Zip: pyzipper remains the ideal choice for its WinZip-compatible AES encryption.Tar: Python's built-in tarfile module is the standard and supports all common tar variations (.tar, .gz, .bz2).

### Conceptual Class Structure:
```
# In lib_archive.py
import pyzipper
import tarfile

def create_archive(archive_path, file_list, base_dir, password=None):
    """Factory function to create an archive based on file extension."""
    if archive_path.endswith('.zip'):
        # ... call zip creation logic ...
    elif archive_path.endswith(('.tar', '.gz', '.bz2')):
        # ... call tar creation logic ...

def extract_archive(archive_path, output_dir, password=None):
    """Factory function to extract an archive."""
    # ... logic to auto-detect format and extract ...

def list_archive_contents(archive_path):
    """Factory function to list contents."""
    # ... logic to auto-detect format and list ...
```

### Command-Line Interface: cli_archive.py
This single script will serve as the entry point for all operations.The desired operation (create, extract, list) will be the first argument.The archive format will be inferred from the filename (e.g., .zip vs .tar.gz) to simplify usage.Revised Example Usage:# Create a new encrypted zip archive

python src/archive_utils/cli_archive.py create my_archive.zip ./source_dir/ --password "secret"

```
# Create a new gzipped tar archive
python src/archive_utils/cli_archive.py create my_docs.tar.gz ./documents/

# Extract a zip file (will prompt for password if encrypted)
python src/archive_utils/cli_archive.py extract my_archive.zip --output-dir ./unpacked_files/

# Extract a tar file
python src/archive_utils/cli_archive.py extract my_docs.tar.gz -o ./docs_out/

# List the contents of any archive
python src/archive_utils/cli_archive.py list my_archive.zip
```

This unified design is more robust, user-friendly, and maintainable than managing separate scripts. It directly addresses your requirements for a focused tool that handles both zip and tar for creation and extraction.
