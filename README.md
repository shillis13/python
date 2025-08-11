# python_libs

Collection of reusable Python utilities, scripts, and helper modules.

## Repository Structure

- `data/` - Schema and configuration data used by the utilities.
- `readmes/` - Additional markdown documentation for bundled tools.
- `scripts/` - Command-line entry points (see [scripts/README.md](scripts/README.md)).
- `src/` - Library source code.
  - `DataTableFunctions/` - Data table helpers, including hierarchical sum algorithms.
  - `ai_utils/` - AI-related helpers for capability reporting, chat continuity, and conversions.
  - `archive_utils/` - Archiving and file backup utilities.
  - `conversions/` - File and chat history conversion tools.
  - `dev_utils/` - Developer-focused helpers such as logging, dry-run, and progress bars.
  - `doc_utils/` - Documentation helpers like manpage generation.
  - `email_tools/` - Email utilities, including a Gmail client.
  - `file_utils/` - File system helpers for finding, renaming, and tree printing.
  - `json_utils/` - JSON manipulation tools for chats and data chunking.
  - `misc/` - Miscellaneous scripts.
  - `packager/` - Tools for packaging chat transcripts.
  - `progressbar/` - Progress bar implementations.
  - `rpatool_master/` - Ren'Py archive manipulation utilities.
  - `terminal_utils/` - Terminal helpers such as history cleaning.
  - `todo/` - Experimental work-in-progress modules.
  - `utils/` - General utility functions and dependency checks.
  - `yaml_utils/` - Extensive YAML helpers and chat history tools.
  - `zip_client/` - Zip file client utilities.
- `tests/` - Automated tests.
- `third_party/` - External or vendored dependencies.
- `tmp/` - Scratch space and temporary files.

## Scripts

See [scripts/README.md](scripts/README.md) for descriptions and usage of the command-line tools in the `scripts/` directory.

