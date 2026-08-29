# CLI Controls

Command-line control utilities and launchers for the AI comms system.

## Overview

This directory contains executable scripts and utilities for managing and controlling the CLI (Command Line Interface) system. Scripts in this directory provide control functions, monitoring, and automation capabilities.

## Scripts

Scripts will be organized here once migrated from their source location. Each script provides specific control or utility functionality.

## Documentation

For detailed architecture documentation, see:
- **Architecture Specification**: `~/Documents/AI/ai_root/ai_comms/docs/cli_controls/cli_controls_architecture_v1.yml`

Additional documentation files are available in the docs directory.

## Directory Structure

```
~/bin/python/src/ai_utils/cli_controls/
├── README.md (this file)
├── [shell scripts]
└── [utility scripts]

~/Documents/AI/ai_root/ai_comms/docs/cli_controls/
├── cli_controls_architecture_v1.yml (main architecture doc)
└── [supporting documentation]

~/Documents/AI/ai_root/ai_comms/scripts/cli_controls/
└── [symlink to ~/bin/python/src/ai_utils/cli_controls]
```

## Setup

To use these scripts, ensure they are executable:

```bash
chmod +x ~/bin/python/src/ai_utils/cli_controls/*.sh
```

## Access Points

- **Scripts directory**: `~/bin/python/src/ai_utils/cli_controls/`
- **Scripts hub symlink**: `~/Documents/AI/ai_root/ai_comms/scripts/cli_controls/`
- **Documentation**: `~/Documents/AI/ai_root/ai_comms/docs/cli_controls/`
