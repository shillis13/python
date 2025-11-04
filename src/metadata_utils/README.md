# Metadata Utils

Tools for extracting and aggregating file and directory metadata.

## Tools

### dir_struct_discovery.py

Crawls directory trees and generates annotated structure views by extracting description metadata from files and READMEs.

**Features:**
- Extracts descriptions from YAML/JSON/Markdown frontmatter
- Parses README.md first paragraphs
- Generates tree, JSON, and Markdown output formats
- Statistics on documentation coverage
- Configurable depth and hidden file handling

**Usage:**
```bash
# Basic scan
dir_struct_discovery.py ~/Documents/AI/Claude/claude_workspace

# Limit depth and output JSON
dir_struct_discovery.py . --depth 2 --format json

# Include hidden files, stats only
dir_struct_discovery.py ~/projects --include-hidden --stats-only

# Show file conventions guide
dir_struct_discovery.py --help-verbose
```

**See Also:**
- `~/bin/python/readmes/file_conventions.md` - File format and metadata standards
