#!/bin/bash
# launch_codex_cli.sh - Create new Codex CLI session
# Usage: ./launch_codex_cli.sh [session_name]
# Returns: Session name (iTerm2 tab identifier)

set -e

# Generate session name if not provided
SESSION_NAME="${1:-codex_cli_$$_${RANDOM}}"

echo "Launching Codex CLI session: $SESSION_NAME" >&2

# Create iTerm2 tab with Codex CLI
osascript <<EOF
tell application "iTerm"
    activate
    tell current window
        -- Create new tab
        set newTab to (create tab with default profile)
        tell current session of newTab
            -- Name the session for identification
            set name to "$SESSION_NAME"
            
            -- Set up environment
            write text "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH"
            delay 0.5
            
            -- Launch Codex CLI
            write text "codex"
            
            return "Session created: $SESSION_NAME"
        end tell
    end tell
end tell
EOF

# Wait for Codex CLI to initialize
echo "Waiting 5 seconds for Codex to initialize..." >&2
sleep 5

# Verify session exists
if osascript -e "tell application \"iTerm\" to repeat with w in windows to repeat with t in tabs of w to repeat with s in sessions of t to if name of s contains \"$SESSION_NAME\" then return \"found\" end repeat end repeat end repeat" | grep -q "found"; then
    echo "✓ Codex CLI session ready: $SESSION_NAME" >&2
    echo "$SESSION_NAME"  # Output session name (NOT PID) for capture
else
    echo "✗ Failed to create session" >&2
    exit 1
fi
