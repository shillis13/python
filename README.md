# python_libs

## Utilities

### `findFiles.py`
Search for files within a directory tree. The script now supports:

- Glob pattern matching (default argument)
- Substring filtering via `--substr`
- Regular expression filtering with `--regex`
- Extension filtering using `--ext`
- File type filtering via `--type` (e.g., `audio`, `video`)
- Recursive search using `-r`
- List available file types with `--list-types`
- Verbose examples using `--verbose-help`

### `dirFileActions.py`
Perform basic file operations such as move, copy and delete. Features include:

- Reading file lists from command line, a file (`--from-file`) or piped input
- Optional glob filtering using `--pattern`
- Ability to operate on directories when `--include-dirs` is supplied
- Dry-run mode enabled by default; use `--exec` to apply changes
