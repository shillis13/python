# Python Source Packages

This directory contains Python utility packages organized by functionality. Each package can be installed independently using pip.

## Package Directory Structure

- **ai_utils** - AI utilities for chat processing, conversion, and codex management
  - `chat_processing/` - Chat format conversion and processing
  - `FILE/` - File liaison and transport utilities
  - `validation/` - Schema validation utilities
  - See "Console Commands" section for 10+ available commands

- **archive_utils** - Archive management and processing utilities

- **DataTableFunctions** - Data table manipulation and processing tools

- **dev_utils** - Development utilities and helper tools

- **doc_utils** - Document processing and manipulation utilities

- **email_tools** - Email handling and processing tools

- **file_utils** - File system utilities for finding, filtering, and formatting
  - See "Console Commands" section for 8 available commands

- **json_utils** - JSON processing and manipulation utilities

- **metadata_utils** - Metadata extraction and management utilities

- **repo_tools** - Repository management and Git utilities

- **terminal_utils** - Terminal and console utilities

- **yaml_utils** - YAML processing and manipulation utilities
  - See "Console Commands" section for 16 available commands

- **zip_client** - ZIP archive utilities

## Installing Packages

### Install All Packages

To install all packages in editable mode (recommended for development):

```bash
./install_packages.sh
```

This installs all packages so that changes to the source code take effect immediately without reinstalling.

### Install a Specific Package

To install just one package:

```bash
./install_packages.sh ai_utils
```

Or manually:

```bash
python3 -m pip install -e ai_utils/
```

### Install Multiple Specific Packages

```bash
./install_packages.sh file_utils yaml_utils json_utils
```

## What is Editable Mode?

The `-e` flag (editable mode) creates a link to the source code rather than copying it. This means:
- Changes to the code take effect immediately
- No need to reinstall after making changes
- Perfect for active development

## Understanding Package Structure

### Top-Level Packages
Each directory with a `setup.py` file is a top-level package that can be installed independently.

### Sub-Packages
Subdirectories within a package (like `ai_utils/chat_processing/`) are **sub-packages** that get included automatically when you install the parent package. They become importable as:

```python
from ai_utils.chat_processing import chat_converter
from file_utils import fsFind
```

### What Gets Included?
The `find_packages()` function in `setup.py` automatically finds all directories containing an `__init__.py` file and includes them as sub-packages.

## Console Commands

After installing packages, these command-line tools become available:

### From ai_utils (10 commands):

**Chat Processing:**
- `batch-md-to-yaml` - Batch convert markdown to YAML
- `chat-chunker` - Split chats into chunks
- `chat-converter` - Convert chat formats
- `chats-splitter` - Split chat files
- `doc-converter` - Convert document formats
- `md-structure-parser` - Parse markdown structure

**Utilities:**
- `codex-manager` - Manage code codex
- `distribute-ai-files` - Distribute AI files
- `simple-schema-validator` - Validate schemas

### From file_utils (8 commands):
- `fsactions` - File system actions
- `fsfilters` - File filtering utilities
- `fsfind` - Advanced file finding
- `fsformat` - File formatting utilities
- `gen-random-files-dirs` - Generate test files/directories
- `pygrep` - Python-based grep
- `rename-files` - Batch file renaming
- `treeprint` - Tree-style directory printing

### From yaml_utils (16 commands):
- `extract-yaml-from-md` - Extract YAML from markdown
- `yaml-add-item` - Add items to YAML
- `yaml-chat-indexer` - Index chat history
- `yaml-chat-manager` - Manage chat files
- `yaml-convert-chat-history` - Convert chat history format
- `yaml-delete-item` - Delete items from YAML
- `yaml-detect-message-gaps` - Find gaps in messages
- `yaml-merge` - Merge YAML files
- `yaml-prune` - Prune YAML content
- `yaml-read-key` - Read YAML keys
- `yaml-shell` - Interactive YAML shell
- `yaml-stats` - YAML statistics
- `yaml-summarize-chat-history` - Summarize chat history
- `yaml-tree-printer` - Print YAML as tree
- `yaml-update-key` - Update YAML keys
- `yaml-validate` - Validate YAML files

## Verifying Installation

After installation, verify packages are installed:

```bash
python3 -m pip list | grep -E "(ai_utils|file_utils|yaml_utils)"
```

Check if console commands are available:

```bash
which chat-converter
which treeprint
```

## Uninstalling

To uninstall a package:

```bash
python3 -m pip uninstall ai_utils
```

To uninstall all packages:

```bash
python3 -m pip uninstall -y ai_utils archive_utils DataTableFunctions dev_utils doc_utils \
  email_tools file_utils json_utils metadata_utils repo_tools terminal_utils \
  yaml_utils zip_client
```

## Development Workflow

1. Install packages in editable mode: `./install_packages.sh`
2. Make changes to the source code
3. Changes take effect immediately (no reinstall needed)
4. Run tests or use console commands to verify
5. When adding new sub-packages, just create a directory with `__init__.py`

## Troubleshooting

**Import errors after installation:**
- Make sure you're using the correct Python environment
- Verify installation with `python3 -m pip list`
- Check that `__init__.py` files exist in package directories

**Console commands not found:**
- Ensure the package's `setup.py` has `entry_points` defined
- Your Python scripts directory must be in PATH
- Try `python3 -m pip install -e package_name/` again

**Permission errors:**
- Use a virtual environment instead of system Python
- Or use `python3 -m pip install --user -e package_name/`

**"pip: command not found" errors:**
- Use `python3 -m pip` instead of `pip` for better compatibility
- This works even if `pip` isn't directly in your PATH
