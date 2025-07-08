# Filter Configuration Examples for lib_filters.py and related utilities
# Save as filters.yml and use with --filter-file or --config option

# =============================================================================
# Example 1: Development Project Cleanup
# Usage: lib_filters.py . --config dev_cleanup.yml
# =============================================================================
dev_cleanup:
  # Target build artifacts and temporary files
  file_patterns:
    - "*.tmp"
    - "*.cache"
    - "*.bak"
    - "*.pyc"
    - "*.pyo"
    - "*.log"
    - "*.swp"
    - "*.swo"
    - "*~"
  
  dir_patterns:
    - "__pycache__"
    - ".pytest_cache"
    - "node_modules"
    - ".venv"
    - "venv"
    - "build"
    - "dist"
    - ".tox"
  
  # Skip recent files (might still be in use)
  modified_before: "7d"
  
  # Only small files (large files might be intentional)
  size_lt: "1M"
  
  # Use git ignore rules
  git_ignore: true

# =============================================================================
# Example 2: Large File Archive
# Usage: fsActions.py --filter-file large_files.yml --move /archive --execute
# =============================================================================
large_files:
  # Only very large files
  size_gt: "100M"
  
  # Older files that haven't been accessed recently
  modified_before: "90d"
  
  # Exclude certain types we want to keep
  file_ignore_patterns:
    - "*.exe"        # Don't archive executables
    - "*.dll"        # Don't archive libraries
    - "*.so"         # Don't archive shared objects
  
  # Only certain file types
  types:
    - "video"
    - "audio"
    - "image"
  
  # Skip empty directories in results
  skip_empty: true

# =============================================================================
# Example 3: Source Code Analysis
# Usage: findFiles.py . --filter-file source_code.yml --recursive
# =============================================================================
source_code:
  # Programming language files
  file_patterns:
    - "*.py"
    - "*.js"
    - "*.ts"
    - "*.java"
    - "*.cpp"
    - "*.c"
    - "*.h"
    - "*.hpp"
    - "*.cs"
    - "*.go"
    - "*.rs"
    - "*.php"
    - "*.rb"
    - "*.swift"
    - "*.kt"
    - "*.scala"
  
  # Exclude certain directories
  dir_ignore_patterns:
    - "node_modules"
    - ".git"
    - ".svn"
    - "__pycache__"
    - "vendor"
    - "third_party"
    - "external"
  
  # Only non-empty files
  size_gt: "1B"
  
  # Use git ignore to skip generated/ignored files
  git_ignore: true

# =============================================================================
# Example 4: Media File Organization
# Usage: fsFormat.py --filter-file media_files.yml --format table --size
# =============================================================================
media_files:
  # Media file types
  types:
    - "image"
    - "video"
    - "audio"
  
  # Reasonable size range (not thumbnails, not huge)
  size_gt: "10K"
  size_lt: "2G"
  
  # Recent files
  modified_after: "30d"
  
  # Exclude certain patterns
  file_ignore_patterns:
    - "thumb*"
    - "preview*"
    - ".*"          # Hidden files
  
  dir_ignore_patterns:
    - ".thumbnails"
    - "cache"
    - "temp"

# =============================================================================
# Example 5: Security Audit
# Usage: lib_filters.py /etc --filter-file security_audit.yml --recursive
# =============================================================================
security_audit:
  # Configuration and sensitive files
  file_patterns:
    - "*.conf"
    - "*.cfg"
    - "*.ini"
    - "*.env"
    - "*passwd*"
    - "*shadow*"
    - "*key*"
    - "*.pem"
    - "*.crt"
    - "*.cert"
  
  # Include hidden files (often config files)
  show_hidden: true
  
  # Recently modified (potential security concern)
  modified_after: "30d"
  
  # Don't use git ignore (want to see everything)
  git_ignore: false

# =============================================================================
# Example 6: Log File Analysis
# Usage: findFiles.py /var/log --filter-file log_analysis.yml --show-stats
# =============================================================================
log_analysis:
  # Log file patterns
  file_patterns:
    - "*.log"
    - "*.log.*"
    - "syslog*"
    - "messages*"
    - "auth.log*"
    - "error.log*"
    - "access.log*"
  
  # Recent logs only
  modified_after: "7d"
  
  # Non-empty logs
  size_gt: "0B"
  
  # Sort by modification time
  sort_by: "modified"
  reverse: true

# =============================================================================
# Example 7: Duplicate File Detection Prep
# Usage: fsFormat.py --filter-file duplicate_prep.yml --format csv --columns name,size,path
# =============================================================================
duplicate_prep:
  # Only files (not directories)
  include_files_only: true
  
  # Minimum size (very small files less likely to be meaningful duplicates)
  size_gt: "1K"
  
  # Exclude certain types that are commonly similar
  file_ignore_patterns:
    - "*.tmp"
    - "*.cache"
    - "*.log"
    - "thumbs.db"
    - ".DS_Store"
  
  # Common document and media types
  types:
    - "document"
    - "image"
    - "video"
    - "audio"

# =============================================================================
# Example 8: Code Quality Check
# Usage: lib_filters.py . --filter-file code_quality.yml --inverse
# =============================================================================
code_quality:
  # Files that shouldn't be in source control
  file_patterns:
    - "*.pyc"
    - "*.pyo"
    - "*.class"
    - "*.o"
    - "*.obj"
    - "*.exe"
    - "*.dll"
    - "*.so"
    - "*.dylib"
    - "*.tmp"
    - "*.log"
    - "*.swp"
    - "*~"
  
  dir_patterns:
    - "__pycache__"
    - ".pytest_cache"
    - "node_modules"
    - "build"
    - "dist"
    - ".git"
    - ".svn"
    - ".hg"
  
  # Use inverse to show files that SHOULD be tracked
  inverse: true
  
  # Respect git ignore
  git_ignore: true

# =============================================================================
# Example 9: Disk Space Analysis
# Usage: fsFormat.py --filter-file disk_space.yml --format table --size --sort-by size --reverse
# =============================================================================
disk_space:
  # Large files taking up space
  size_gt: "10M"
  
  # Include directories to see folder sizes
  include_dirs: true
  
  # Don't filter by type - want to see everything large
  
  # Sort by size (largest first when used with --reverse)
  sort_by: "size"
  reverse: true

# =============================================================================
# Example 10: Recent Activity Monitor
# Usage: findFiles.py . --filter-file recent_activity.yml --recursive --show-stats
# =============================================================================
recent_activity:
  # Very recent files
  modified_after: "1d"
  
  # Include all file types
  
  # Exclude system/temporary patterns
  file_ignore_patterns:
    - "*.tmp"
    - "*.log"
    - "*.cache"
    - ".DS_Store"
    - "thumbs.db"
  
  dir_ignore_patterns:
    - ".git"
    - "__pycache__"
    - "node_modules"
  
  # Sort by modification time
  sort_by: "modified"
  reverse: true

# =============================================================================
# Usage Instructions:
# 
# 1. Save specific sections to individual YAML files
# 2. Use with any of the utilities:
#    - lib_filters.py . --config dev_cleanup.yml
#    - fsActions.py --filter-file large_files.yml --move /archive
#    - findFiles.py . --filter-file source_code.yml --recursive
#    - fsFormat.py --filter-file media_files.yml --format table
#
# 3. Combine with command line options:
#    - findFiles.py . --filter-file source_code.yml --size-gt 100K --recursive
#    - fsActions.py --filter-file large_files.yml --copy /backup --with-dir
#
# 4. Create custom configurations by mixing and matching options
#
# =============================================================================
