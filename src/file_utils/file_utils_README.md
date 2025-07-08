# Enhanced File Utilities System

A comprehensive and modular file system utility suite with powerful filtering, formatting, and operation capabilities.

## Recent Refactoring Overview

This file utilities system has undergone comprehensive refactoring into a unified, modular system with shared filtering capabilities and enhanced functionality. The refactoring transformed four core utilities with expanded capabilities:

### Refactored Utilities Summary

**fsFilters.py** (formerly ignore_filter.py) - Central filtering system with size filtering (`--size-gt 1M`), date filtering (`--modified-after 7d`), pattern filtering (`--file-pattern "*.py"`), type/extension filtering (`--type image`), Git integration (`--git-ignore`), and YAML configuration support.

**fsActions.py** (formerly fsActions.py) - Enhanced file operations with structure preservation (`--with-dir`), permission management (`--set-permissions 755`), attribute modification, and full fsFilters.py integration with safety defaults.

**fsFormat.py** (formerly treePrint.py) - Multi-format display supporting tree, table, JSON, YAML, and CSV formats with customizable columns, sorting, grouping, and comprehensive filtering integration.

**fsFind.py** (Enhanced) - Advanced file discovery maintaining backward compatibility while adding fsFilters.py integration, git-aware searching, enhanced statistics (`--show-stats`), and comprehensive help systems.

### Key Architectural Improvements

- **Unified Filtering Engine**: Shared filtering logic across all utilities with consistent command-line interface and YAML configuration support
- **Safety and Usability**: Dry-run defaults for destructive operations, comprehensive help systems, statistics reporting, and graceful error handling  
- **Pipeline Integration**: Tools designed to work together seamlessly with standard input/output handling and format compatibility
- **Performance Optimization**: Git-aware filtering, early filtering to reduce processing, efficient directory traversal, and smart caching

## Overview

This refactored file utilities system provides a cohesive set of tools for file system operations, built around a central filtering system that ensures consistency and reusability across all utilities.

## Core Components

### 1. fsFilters.py - Central Filtering System

The foundation of the entire system, providing comprehensive filtering capabilities:

- **Size Filtering**: `--size-gt 1M`, `--size-lt 100M`, `--size-eq 0`
- **Date Filtering**: `--modified-after 7d`, `--created-before 2024-01-01`
- **Pattern Filtering**: `--file-pattern "*.py"`, `--dir-pattern "test*"`
- **Type Filtering**: `--type image`, `--extension py`
- **Git Integration**: `--git-ignore`, `--ignore-file .dockerignore`
- **Special Options**: `--inverse`, `--skip-empty`, `--show-empty`

```bash
# Examples
fsFilters.py . --size-gt 1M --modified-after 30d --git-ignore
fsFilters.py . --type image --size-lt 10M --inverse
fsFilters.py . --config filters.yml --dry-run
```

### 2. fsActions.py - Enhanced File Operations

Previously `fsActions.py`, now with advanced filtering and structure preservation:

- **Operations**: `--move`, `--copy`, `--delete`
- **Structure Control**: `--with-dir`, `--base-path`
- **Attribute Management**: `--set-permissions 755`, `--set-mtime`
- **Integrated Filtering**: All fsFilters.py options available

```bash
# Examples
fsActions.py --move /backup --size-gt 100M --modified-before 90d --execute
fsActions.py --copy /dest --with-dir --type image --git-ignore --execute
fsActions.py --delete --pattern "*.tmp" --filter-file cleanup.yml --execute
```

### 3. fsFormat.py - Multi-Format Display

Previously `treePrint.py`, now supporting multiple output formats:

- **Formats**: `--tree`, `--table`, `--json`, `--yaml`, `--csv`
- **Content Options**: `--files`, `--size`, `--modified`, `--permissions`
- **Customization**: `--columns name,size,modified`, `--sort-by size --reverse`
- **Tree Options**: `--ascii`, `--no-colors`, `--max-depth 3`

```bash
# Examples
fsFormat.py . --tree --files --size --modified
fsFormat.py . --table --columns name,size,type --sort-by size --reverse
fsFormat.py . --json --type image --git-ignore > images.json
fsFormat.py . --csv --size-gt 1M --columns name,size,path > large_files.csv
```

### 4. fsFind.py - Enhanced File Discovery

Enhanced with full fsFilters.py integration while maintaining backward compatibility:

- **Legacy Support**: All original options preserved
- **Enhanced Filtering**: Full fsFilters.py integration
- **Performance**: Git-aware searching, smart recursion
- **Statistics**: `--show-stats`, `--dry-run`

```bash
# Examples (legacy)
fsFind.py . "*.py" --recursive --ext py
fsFind.py . --substr test --type image

# Examples (enhanced)
fsFind.py . --file-pattern "*.py" --size-gt 10K --git-ignore --recursive
fsFind.py . --filter-file search.yml --show-stats
```

## Key Features

### Unified Filtering System

All utilities share the same filtering engine via fsFilters.py:

- **Consistent Interface**: Same options work across all tools
- **YAML Configuration**: Complex filters in reusable config files
- **Pipeline Friendly**: Tools work together seamlessly
- **Git Integration**: Respects .gitignore files automatically

### Directory Structure Preservation

Enhanced support for maintaining directory hierarchies:

```bash
# Flat copy (default)
fsActions.py --copy /backup *.log --execute

# Preserve structure
fsActions.py --copy /backup --with-dir --base-path /project *.log --execute
```

### Multiple Output Formats

fsFormat.py supports various output formats for different use cases:

- **Tree**: Visual exploration and documentation
- **Table**: Human-readable structured data
- **JSON**: Programmatic processing and APIs
- **YAML**: Configuration and structured documentation
- **CSV**: Spreadsheet analysis and data processing

### Configuration Files

YAML configuration files provide reusable, complex filter combinations:

```yaml
# development_cleanup.yml
file_patterns:
  - "*.tmp"
  - "*.cache"
  - "*.pyc"
dir_patterns:
  - "__pycache__"
  - "node_modules"
size_lt: "1M"
modified_before: "7d"
git_ignore: true
```

### Pipeline Integration

All utilities work together in command pipelines:

```bash
# Find large images, format as table, archive to /backup
fsFind.py . --type image --size-gt 10M -r | \
fsFormat.py --format table --size --modified | \
fsActions.py --move /backup --with-dir --execute

# Filter files by criteria, output as JSON
fsFilters.py . --config filters.yml | \
fsFormat.py --format json --files > filtered_files.json

# Find and clean up build artifacts
fsFind.py . --filter-file cleanup.yml -r | \
fsActions.py --delete --dry-run  # preview first
```

## Usage Patterns

### Development Workflow

```bash
# Find source code files
fsFind.py . --file-pattern "*.py" --file-pattern "*.js" --git-ignore -r

# Format project structure
fsFormat.py . --tree --files --git-ignore --max-depth 3

# Archive large old files
fsActions.py --move /archive --size-gt 100M --modified-before 180d --with-dir -x

# Clean up build artifacts
fsFilters.py . --config dev_cleanup.yml | fsActions.py --delete --execute
```

### System Administration

```bash
# Find large log files
fsFind.py /var/log --pattern "*.log" --size-gt 100M --modified-before 30d

# Security audit - find recently modified config files
fsFind.py /etc --pattern "*.conf" --modified-after 7d --recursive --show-stats

# Disk usage analysis
fsFormat.py /home --table --size --sort-by size --reverse --size-gt 1G

# Backup user data with structure preservation
fsActions.py --copy /backup --with-dir --base-path /home --type document --execute
```

### Media Management

```bash
# Find and organize images
fsFind.py ~/Pictures --type image --size-gt 1M -r | \
fsFormat.py --format table --size --modified --columns name,size,modified,path

# Archive old videos
fsActions.py --move /archive/videos --type video --modified-before 1y --with-dir -x

# Export media metadata to CSV
fsFormat.py ~/Media --csv --type image,video --columns name,size,modified,path > media_inventory.csv
```

## Configuration Reference

### YAML Filter Configuration

```yaml
# Complete example showing all available options
filter_config:
  # Size filters
  size_gt: "1M"      # Greater than 1 megabyte
  size_lt: "100M"    # Less than 100 megabytes
  size_eq: "0"       # Exactly 0 bytes (empty files)
  
  # Date filters
  modified_after: "7d"           # Last 7 days
  modified_before: "2024-01-01"  # Before specific date
  created_after: "1w"            # Last week
  created_before: "30d"          # Before 30 days ago
  
  # Pattern filters
  file_patterns:
    - "*.py"
    - "*.js"
    - "test_*"
  dir_patterns:
    - "src*"
    - "lib*"
  file_ignore_patterns:
    - "*.tmp"
    - "*.cache"
  dir_ignore_patterns:
    - "__pycache__"
    - "node_modules"
  
  # Type and extension filters
  types:
    - "image"
    - "video"
  extensions:
    - "py"
    - "js"
    - "md"
  
  # Special options
  git_ignore: true
  inverse: false
  skip_empty: true
  show_empty: false
```

### Command Line Options

All utilities support these common options:

- `--filter-file FILE` - Load configuration from YAML file
- `--dry-run` - Preview operations without execution
- `--help-examples` - Show usage examples
- `--help-verbose` - Show comprehensive help

## Installation and Setup

1. **Dependencies**: Ensure all utilities have access to the shared modules:
   ```
   src/
   ├── dev_utils/
   │   ├── lib_logging.py
   │   ├── lib_dryrun.py
   │   ├── lib_outputColors.py
   │   └── lib_argparse_registry.py
   ├── file_utils/
   │   ├── fsFilters.py         # Central filtering system
   │   ├── lib_extensions.py      # File type definitions
   │   ├── lib_fileinput.py       # Input handling utilities
   │   ├── fsActions.py           # File operations (was fsActions.py)
   │   ├── fsFormat.py            # Multi-format display (was treePrint.py)
   │   └── fsFind.py           # Enhanced file finding
   ```

2. **Python Path**: Make sure the `src` directory is in your Python path

3. **Extensions Data**: Ensure `extensions.yml` is available in data/ or current directory

4. **Testing**: Test each utility with `--help` and `--dry-run` options

## Advanced Features

### Empty Directory Handling

```bash
# Skip empty directories in output
fsFilters.py . --skip-empty

# Show only empty directories
fsFilters.py . --show-empty

# Clean up empty directories
fsFilters.py . --show-empty | fsActions.py --delete --execute
```

### Git Integration

```bash
# Respect .gitignore files
fsFind.py . --git-ignore --recursive

# Find only ignored files (useful for cleanup)
fsFilters.py . --git-ignore --inverse

# Use custom ignore file
fsFilters.py . --ignore-file .dockerignore
```

### Performance Optimization

```bash
# Preview operations before execution
fsActions.py --move /backup --size-gt 1G --dry-run

# Show statistics for large operations
fsFind.py /large/directory --recursive --show-stats

# Use filters to reduce search scope
fsFind.py . --git-ignore --type source --recursive
```

## Migration from Legacy Tools

### fsActions.py → fsActions.py

- All original functionality preserved
- Add `--with-dir` for structure preservation
- Use `--filter-file` for complex filtering
- Add `--execute` for safety (replaces `--exec`)

### treePrint.py → fsFormat.py

- Tree format is default (use `--tree` explicitly if needed)
- Add `--format table|json|yaml|csv` for other formats
- Use `--columns` to customize table/CSV output
- Add filtering with `--filter-file`

### ignore_filter.py → fsFilters.py

- Much more comprehensive filtering options
- YAML configuration file support
- Git integration built-in
- Size and date filtering added

### fsFind.py (Enhanced)

- All legacy options preserved for backward compatibility
- Add `--filter-file` for complex searches
- Enhanced performance with git-aware searching
- Better statistics and dry-run support

## Best Practices

1. **Use Configuration Files**: For complex filters, use YAML files for reusability
2. **Preview First**: Always use `--dry-run` for destructive operations
3. **Leverage Git Integration**: Use `--git-ignore` for cleaner, faster operations
4. **Pipeline Efficiently**: Combine tools for powerful workflows
5. **Check Statistics**: Use `--show-stats` to verify operation scope
6. **Preserve Structure**: Use `--with-dir` when moving/copying to maintain organization

## Troubleshooting

### Common Issues

1. **Permission Errors**: Tools gracefully handle permission issues and report statistics
2. **Large Directories**: Use `--max-depth` and filtering to manage performance
3. **Complex Filters**: Test with `--dry-run` and `--show-stats` first
4. **Configuration Errors**: YAML syntax errors are reported with helpful messages

### Performance Tips

1. Use `--git-ignore` to skip irrelevant files
2. Combine size and date filters to narrow scope
3. Use specific patterns rather than broad searches
4. Preview operations with `--dry-run` for large datasets

## Examples Repository

See the configuration examples in `filter_config_examples.yml` for ready-to-use filter configurations for common scenarios:

- Development project cleanup
- Large file archival
- Source code analysis
- Media file organization
- Security audits
- Log file analysis
- Duplicate detection preparation
- Code quality checks
- Disk space analysis
- Recent activity monitoring

Each example includes usage instructions and can be saved as individual YAML files for specific use cases.

## Supporting Infrastructure

### Configuration System
- **extensions.yml**: Comprehensive file type definitions with hierarchical categories
- **extensions.schema.yml**: Validation schema for type definitions ensuring data consistency
- **filter_config_examples.yml**: Ready-to-use filter configurations for common scenarios
- **YAML configuration support**: All utilities support `--filter-file` for complex operations

### Documentation
- **Enhanced README**: Complete system documentation with usage patterns and examples
- **Usage examples**: Comprehensive examples for all utilities covering basic to advanced use cases
- **Pipeline integration**: Examples of tool combinations and workflow automation
- **Migration guide**: Backward compatibility notes and upgrade instructions
