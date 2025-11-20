#!/bin/bash
# send_to_cli.sh - Send command to CLI session
# Usage: ./send_to_cli.sh <session_name> "command text"
# 
# Works with any CLI session (Claude, Codex, etc) - just needs session name

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session_name> \"command text\""
    echo ""
    echo "Session name is returned by launch_*_cli.sh scripts"
    exit 1
fi

SESSION_NAME="$1"
COMMAND="$2"

echo "Sending to CLI ($SESSION_NAME): $COMMAND" >&2

# Send command via iTerm2 write text (more reliable than keystroke)
RESULT=$(osascript - "$SESSION_NAME" "$COMMAND" <<'OSA'
on run argv
  set sessionName to item 1 of argv
  set commandText to item 2 of argv
  
  tell application "iTerm2"
    repeat with aWindow in windows
      repeat with aTab in tabs of aWindow
        repeat with aSession in sessions of aTab
          if (name of aSession) contains sessionName then
            tell aSession
              write text commandText
            end tell
            return "Command sent to: " & (name of aSession)
          end if
        end repeat
      end repeat
    end repeat
    return "ERROR: Session not found: " & sessionName
  end tell
end run
OSA
)

if echo "$RESULT" | grep -q "ERROR"; then
    echo "✗ $RESULT" >&2
    exit 1
else
    echo "✓ $RESULT" >&2
fi
