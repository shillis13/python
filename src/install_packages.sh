#!/usr/bin/env bash
# install_packages.sh - Install Python packages in editable mode
#
# Usage:
#   ./install_packages.sh                        # Install all packages
#   ./install_packages.sh --rebuild              # Rebuild setup.py files and install all
#   ./install_packages.sh ai_utils               # Install specific package
#   ./install_packages.sh --rebuild file_utils   # Rebuild and install specific package

set -e  # Exit on error

# Function to show help
show_help() {
    cat <<EOF
${BLUE}install_packages.sh${NC} - Install Python packages in editable mode

${BLUE}USAGE:${NC}
    ./install_packages.sh [OPTIONS] [PACKAGE...]

${BLUE}OPTIONS:${NC}
    --help              Show this help message and exit
    --rebuild           Rebuild setup.py files before installing
                        Auto-discovers scripts and updates entry_points

${BLUE}EXAMPLES:${NC}
    ${GREEN}# Install all packages${NC}
    ./install_packages.sh

    ${GREEN}# Install specific packages${NC}
    ./install_packages.sh ai_utils file_utils

    ${GREEN}# Rebuild setup.py files and install all${NC}
    ./install_packages.sh --rebuild

    ${GREEN}# Rebuild and install specific packages${NC}
    ./install_packages.sh --rebuild yaml_utils

${BLUE}AVAILABLE PACKAGES:${NC}
    ai_utils            AI utilities (chat processing, codex manager)
    archive_utils       Archive management tools
    DataTableFunctions  Data table manipulation
    dev_utils           Development utilities
    doc_utils           Document processing
    email_tools         Email handling tools
    file_utils          File system utilities (fsfind, treeprint, etc.)
    json_utils          JSON processing
    metadata_utils      Metadata extraction
    repo_tools          Repository/Git utilities
    terminal_utils      Terminal utilities
    yaml_utils          YAML processing (16+ commands)
    zip_client          ZIP archive tools

${BLUE}WHAT IS EDITABLE MODE?${NC}
    The -e flag installs packages as links to source code, so changes
    take effect immediately without reinstalling.

${BLUE}WHAT DOES --rebuild DO?${NC}
    Scans each package for executable Python scripts (excluding lib_*,
    test_*, and __* files) and automatically updates setup.py with
    console_scripts entry points. Use this when you:
    - Add new executable scripts
    - Remove scripts
    - Want to ensure setup.py is up-to-date

${BLUE}CONSOLE COMMANDS:${NC}
    After installation, 34+ command-line tools become available:
    - From ai_utils: chat-converter, doc-converter, codex-manager, etc.
    - From file_utils: fsfind, treeprint, rename-files, etc.
    - From yaml_utils: yaml-merge, yaml-validate, yaml-shell, etc.

    Run 'which chat-converter' to verify commands are installed.

${BLUE}MORE INFO:${NC}
    See README.md for complete documentation and package details.
EOF
    exit 0
}

# Parse flags
REBUILD_SETUP=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            ;;
        --rebuild)
            REBUILD_SETUP=true
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# List of all packages (directories with setup.py)
ALL_PACKAGES=(
    "ai_utils"
    "archive_utils"
    "DataTableFunctions"
    "dev_utils"
    "doc_utils"
    "email_tools"
    "file_utils"
    "json_utils"
    "metadata_utils"
    "repo_tools"
    "terminal_utils"
    "yaml_utils"
    "zip_client"
)

# Function to check if a directory has setup.py
has_setup() {
    local dir="$1"
    [[ -f "$SCRIPT_DIR/$dir/setup.py" ]]
}

# Function to find executable scripts in a package (excluding lib_, test_, __* files)
find_executable_scripts() {
    local pkg_dir="$1"
    local scripts=()

    # Find Python files that are likely executable (not lib_, test_, or __* files)
    while IFS= read -r file; do
        local basename=$(basename "$file" .py)
        # Skip if file is lib_, test_, setup, or __*
        if [[ "$basename" =~ ^lib_ ]] || [[ "$basename" =~ ^test_ ]] || \
           [[ "$basename" == "setup" ]] || [[ "$basename" =~ ^__ ]]; then
            continue
        fi

        # Check if file has main() or if __name__ == __main__
        if grep -q "def main" "$file" 2>/dev/null || \
           grep -q "if __name__.*==.*__main__" "$file" 2>/dev/null; then
            scripts+=("$basename")
        fi
    done < <(find "$pkg_dir" -maxdepth 2 -name "*.py" -type f)

    printf '%s\n' "${scripts[@]}"
}

# Function to rebuild setup.py with discovered scripts
rebuild_setup_py() {
    local pkg="$1"
    local pkg_dir="$SCRIPT_DIR/$pkg"

    echo -e "${BLUE}  Scanning for executable scripts in $pkg...${NC}"

    # Find all executable scripts
    local scripts=()
    mapfile -t scripts < <(find_executable_scripts "$pkg_dir")

    if [[ ${#scripts[@]} -eq 0 ]]; then
        echo -e "${YELLOW}  No executable scripts found, skipping setup.py rebuild${NC}"
        return 0
    fi

    echo -e "${GREEN}  Found ${#scripts[@]} executable script(s)${NC}"

    # Read existing setup.py
    local setup_file="$pkg_dir/setup.py"
    if [[ ! -f "$setup_file" ]]; then
        echo -e "${RED}  setup.py not found${NC}"
        return 1
    fi

    # Create entry_points section
    local entry_points="    # Console scripts - auto-generated\n"
    entry_points+="    entry_points={\n"
    entry_points+="        'console_scripts': [\n"

    for script in "${scripts[@]}"; do
        # Determine the module path
        local script_file=$(find "$pkg_dir" -name "${script}.py" -type f | head -1)

        # Skip if script file not found
        if [[ -z "$script_file" ]]; then
            echo -e "${YELLOW}    Warning: Could not find ${script}.py, skipping${NC}"
            continue
        fi

        local rel_path=$(python3 -c "import os; print(os.path.relpath('$script_file', '$pkg_dir'))")
        local module_path=$(echo "$rel_path" | sed 's/\.py$//' | sed 's/\//./g')

        # Keep script name as-is (with underscores)
        local cmd_name="$script"

        entry_points+="            '$cmd_name=${pkg}.${module_path}:main',\n"
    done

    entry_points+="        ],\n"
    entry_points+="    },"

    # Check if entry_points already exists in setup.py
    if grep -q "entry_points" "$setup_file"; then
        echo -e "${YELLOW}  Updating existing entry_points in setup.py${NC}"
        # Use Python to properly update the setup.py
        python3 <<EOF
import re

with open('$setup_file', 'r') as f:
    content = f.read()

# Remove existing entry_points section
content = re.sub(r'\s*#[^\n]*Console scripts[^\n]*\n\s*entry_points=\{[^}]+\},?\s*', '\n', content, flags=re.DOTALL)

# Add new entry_points before the last closing parenthesis
entry_points = '''
$(echo -e "$entry_points")
'''

# Find the last ) before end of file
content = re.sub(r'(\n\)\s*$)', entry_points + r'\n)', content)

with open('$setup_file', 'w') as f:
    f.write(content)
EOF
    else
        echo -e "${YELLOW}  Adding entry_points to setup.py${NC}"
        # Add entry_points before final closing paren
        python3 <<EOF
with open('$setup_file', 'r') as f:
    content = f.read()

entry_points = '''
$(echo -e "$entry_points")
'''

# Add before final )
content = content.rstrip()
if content.endswith(')'):
    content = content[:-1] + entry_points + '\n)'
else:
    content += entry_points

with open('$setup_file', 'w') as f:
    f.write(content)
EOF
    fi

    echo -e "${GREEN}  ✓ setup.py updated${NC}"
}

# Function to install a package
install_package() {
    local pkg="$1"
    local pkg_path="$SCRIPT_DIR/$pkg"

    if [[ ! -d "$pkg_path" ]]; then
        echo -e "${RED}✗ Directory not found: $pkg${NC}"
        return 1
    fi

    if ! has_setup "$pkg"; then
        echo -e "${YELLOW}⚠ No setup.py found in $pkg, skipping${NC}"
        return 1
    fi

    # Rebuild setup.py if requested
    if [[ "$REBUILD_SETUP" == "true" ]]; then
        rebuild_setup_py "$pkg"
    fi

    echo -e "${BLUE}Installing $pkg...${NC}"
    # Use python3 -m pip for better compatibility
    # Try different installation methods in order of preference:
    # 1. Normal install (works in venv)
    # 2. User install
    # 3. Break system packages (needed for Homebrew Python 3.14+)
    if python3 -m pip install -e "$pkg_path" 2>/dev/null; then
        echo -e "${GREEN}✓ Successfully installed $pkg${NC}"
        return 0
    elif python3 -m pip install --user -e "$pkg_path" 2>/dev/null; then
        echo -e "${GREEN}✓ Successfully installed $pkg (user install)${NC}"
        return 0
    elif python3 -m pip install --break-system-packages -e "$pkg_path"; then
        echo -e "${GREEN}✓ Successfully installed $pkg (system packages)${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to install $pkg${NC}"
        return 1
    fi
}

# Main script logic
main() {
    local packages_to_install=()
    local success_count=0
    local fail_count=0
    local skip_count=0

    # Determine which packages to install
    if [[ $# -eq 0 ]]; then
        # No arguments - install all packages
        if [[ "$REBUILD_SETUP" == "true" ]]; then
            echo -e "${BLUE}Rebuilding setup.py files and installing all packages...${NC}\n"
        else
            echo -e "${BLUE}Installing all packages in editable mode...${NC}\n"
        fi
        packages_to_install=("${ALL_PACKAGES[@]}")
    else
        # Specific packages requested
        if [[ "$REBUILD_SETUP" == "true" ]]; then
            echo -e "${BLUE}Rebuilding setup.py files and installing specified packages...${NC}\n"
        else
            echo -e "${BLUE}Installing specified packages in editable mode...${NC}\n"
        fi
        packages_to_install=("$@")
    fi

    # Install each package
    for pkg in "${packages_to_install[@]}"; do
        if install_package "$pkg"; then
            success_count=$((success_count + 1))
        elif has_setup "$pkg"; then
            fail_count=$((fail_count + 1))
        else
            skip_count=$((skip_count + 1))
        fi
        echo ""
    done

    # Print summary
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}Installation Summary${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Successful: $success_count${NC}"
    [[ $fail_count -gt 0 ]] && echo -e "${RED}✗ Failed: $fail_count${NC}"
    [[ $skip_count -gt 0 ]] && echo -e "${YELLOW}⚠ Skipped: $skip_count${NC}"
    echo ""

    # List installed packages
    if [[ $success_count -gt 0 ]]; then
        echo -e "${BLUE}Verifying installed packages:${NC}"
        python3 -m pip list | grep -E "(ai_utils|archive_utils|DataTableFunctions|dev_utils|doc_utils|email_tools|file_utils|json_utils|metadata_utils|repo_tools|terminal_utils|yaml_utils|zip_client)" || true
        echo ""
    fi

    # Check for console commands
    local has_commands=false
    if command -v chat-converter &> /dev/null; then
        if [[ "$has_commands" == "false" ]]; then
            echo -e "${BLUE}Available console commands:${NC}"
            has_commands=true
        fi
        echo "  - chat-converter (from ai_utils)"
        echo "  - doc-converter (from ai_utils)"
        echo "  - chats-splitter (from ai_utils)"
    fi

    if command -v treeprint &> /dev/null; then
        if [[ "$has_commands" == "false" ]]; then
            echo -e "${BLUE}Available console commands:${NC}"
            has_commands=true
        fi
        echo "  - fsfind (from file_utils)"
        echo "  - fsformat (from file_utils)"
        echo "  - treeprint (from file_utils)"
        echo "  - rename-files (from file_utils)"
    fi

    [[ "$has_commands" == "true" ]] && echo ""

    # Exit with error if any installations failed
    [[ $fail_count -gt 0 ]] && exit 1
    exit 0
}

# Run main function
main "$@"
