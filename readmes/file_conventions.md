# File Format and Directory Structure Conventions

**Version:** 1.0.0  
**Last Updated:** 2025-11-03  
**Maintainer:** PianoMan

---

## Purpose
- Establish YAML as canonical source format for structured data
- Define metadata standards for file and directory documentation
- Enable automated discovery and aggregation tools
- Document directory structure patterns for navigation

---

## File Metadata Standards

### Required Description Headers

**All structured files (YAML, JSON, Markdown) must include a brief description for programmatic extraction.**

#### YAML Files
```yaml
---
title: Protocol Name
version: 1.0.0
description: "Brief 1-2 sentence description of what this file contains and its purpose."
last_updated: 2025-11-03
maintainer: PianoMan
status: active
---

# Rest of content...
```

#### JSON Files
```json
{
  "_meta": {
    "title": "Configuration Name",
    "description": "Brief 1-2 sentence description of what this file contains and its purpose.",
    "version": "1.0.0",
    "last_updated": "2025-11-03"
  },
  "actual_data": {
    ...
  }
}
```

#### Markdown Files
```markdown
---
title: Document Name
description: "Brief 1-2 sentence description of what this document covers."
version: 1.0.0
last_updated: 2025-11-03
---

# Document Content
```

### Description Guidelines
- **Length:** 1-2 sentences, max 200 characters
- **Content:** What the file contains, not how to use it
- **Clarity:** Assume reader knows nothing about the project
- **Actionable:** Reader should know if they need to read the full file

**Good examples:**
- "CLI coordination protocol v3.1 specification defining file-based task management between Desktop Claude and CLI instances."
- "Memory digest of MCP configuration troubleshooting and Desktop automation tool development."
- "Architecture principles requiring standard interfaces (MCP, OpenAPI) over tool-specific implementations."

**Bad examples:**
- "Important file" (too vague)
- "Contains the comprehensive detailed specification..." (too long)
- "Read this first" (not descriptive)

---

## Directory Documentation Standards

### README.md Requirements

**Every directory must contain a README.md with:**
1. Brief description (1-3 sentences) of directory purpose
2. Contents overview (optional, for complex directories)
3. Navigation hints (optional, where to go next)

**Maximum length:** ~15 lines total. This is a signpost, not documentation.

### README.md Template
```markdown
# Directory Name

Brief 1-3 sentence description of what this directory contains and why it exists.

## Contents
- `file1.yml` - One line description
- `subdir/` - One line description

## See Also
- Related directory or parent context
```

---

## Source Data Format: YAML

### YAML as Source of Truth
- **Structured data** (configs, protocols, specifications) → YAML is source
- **Generated Markdown** (`.yml.md` files) are human-readable pretty-prints
- **Edit YAML files** when making changes, regenerate MD versions
- **Context optimization** - YAML loads on-demand, MD auto-loads (token cost difference)

### File Relationships
```
protocol_v3.yml          # SOURCE - edit this
protocol_v3.yml.md       # GENERATED - for humans, regenerate after edits
```

### Not All MD Files Are Generated
**Primary Markdown:**
- `README.md` - Documentation (hand-written)
- `notes.md` - Task notes (hand-written)
- `CHANGELOG.md` - History (hand-maintained)

**Generated Markdown:**
- `*.yml.md` - Pretty-printed from YAML
- Auto-generated reports

**Rule of thumb:** If there's a `.yml` file with same base name, the `.md` is generated.

---

## Directory Structure Patterns

### Numbered Directories
Numeric prefixes indicate ordering or categorization:

```
~/Documents/AI/
├── 00_inbox/              # Incoming items, unsorted
├── 05_memories/           # Memory digests and context
│   ├── 10_archive/        # Historical, rarely accessed
│   ├── 50_active/         # Current working context
│   └── 90_templates/      # Reusable templates
├── 10_projects/           # Active development work
├── 20_tools/              # Scripts and utilities
├── 30_data/               # Raw data and datasets
└── 40_digests/            # Processed summaries
```

**Numbering scheme:**
- **00-09:** Temporary/transient (inbox, scratch)
- **10-19:** Active work
- **20-29:** Tools and utilities
- **30-39:** Data and resources
- **40-49:** Processed outputs
- **50-59:** Active/current state
- **80-89:** Configuration and settings
- **90-99:** Templates and archives

### Common Directory Names

**Standard patterns:**
- `bin/` - Executable scripts
- `data/` - Data files, inputs, outputs
- `docs/` - Documentation
- `src/` - Source code
- `tests/` - Test files
- `tmp/` or `temp/` - Temporary files
- `archive/` - Old/inactive content
- `templates/` - Reusable patterns

**AI-specific:**
- `coordination/` - CLI coordination protocol
- `broadcasts/` - Tasks for any CLI
- `direct/` - Assigned to specific instances
- `responses/` - Completed work results
- `announcements/` - Inter-AI messaging

### File Naming Conventions

**Prefixes indicate purpose:**
- `instr_*.md` - Instruction files
- `spec_*.yml` - Specifications
- `protocol_*.md` - Protocol definitions
- `task_*` - TODO system tasks
- `req_NNNN_*.md` - CLI coordination requests

**Version suffixes:**
- `*_v1.md` or `*_v01.yml` - Versioned documents
- `*_draft.md` - Work in progress
- `*_YYYYMMDD.md` - Date-stamped versions

---

## Context Window Optimization

### File Format Impact on Token Usage
**Markdown files:**
- Auto-load into context as project knowledge
- Full content counts against token limit
- Use for small, frequently needed docs

**YAML files:**
- Load on-demand via `view` tool
- Only consume tokens when explicitly read
- Use for large structured data

**Strategy:**
- Keep frequently accessed, small docs in `.md`
- Keep large, occasionally needed data in `.yml`
- Generate `.yml.md` for human review without context cost
- Can have 2-3x longer conversations with YAML approach

### File Size Guidelines
**Auto-load as Markdown (<10KB):**
- Core instructions
- Frequently referenced specs
- Quick reference guides

**Keep as YAML (>10KB):**
- Large memory digests
- Comprehensive protocols
- Detailed specifications
- Historical archives

---

## Quick Reference

### File Format Decision Tree
```
Is it structured data? (protocol, spec, config, digest)
├─ YES → Use YAML as source
│  ├─ Small (<5KB)? → Keep MD version too
│  └─ Large (>5KB)? → YAML only, generate .yml.md on demand
└─ NO → Is it prose/documentation?
   ├─ YES → Markdown primary
   └─ NO → Use appropriate format (code, CSV, JSON, etc.)
```

### Directory Navigation Tips
```bash
# Find files by type
find ~/Documents/AI -name "instr_*.md"
find ~/Documents/AI -name "*.yml" -not -name "*.yml.md"

# Check directory structure
tree -L 2 ~/Documents/AI/

# Generate annotated structure
dir_struct_discovery.py ~/Documents/AI/Claude/claude_workspace
```

---

## See Also
- `dir_struct_discovery.py --help` - Directory structure aggregation tool
- `~/Documents/AI/ai_general/instructions/` - AI-facing instruction files
