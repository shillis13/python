#!/bin/bash
# kill_cli.sh - Close CLI session
# Usage: ./kill_cli.sh <session_name>
#
# Works with any CLI session - just needs session name from launch script

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session_name>"
    echo ""
    echo "Session name is returned by launch_*_cli.sh scripts"
    exit 1
fi

SESSION_NAME="$1"

echo "Closing CLI session: $SESSION_NAME" >&2

# Close the iTerm2 session
RESULT=$(osascript <<EOF
tell application "iTerm"
    repeat with aWindow in windows
        repeat with aTab in tabs of aWindow
            repeat with aSession in sessions of aTab
                if name of aSession contains "$SESSION_NAME" then
                    close aSession
                    return "Closed session: " & name of aSession
                end if
            end repeat
        end repeat
    end repeat
    
    return "ERROR: Session not found: $SESSION_NAME"
end tell
EOF
)

if echo "$RESULT" | grep -q "ERROR"; then
    echo "✗ $RESULT" >&2
    exit 1
else
    echo "✓ $RESULT" >&2
fi
