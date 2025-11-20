#!/bin/bash
# launch_claude_cli.sh - Create new Claude CLI session  
# Usage: ./launch_claude_cli.sh [session_name]
# Returns: Session name (iTerm2 tab identifier)

set -e

# Generate session name if not provided
SESSION_NAME="${1:-claude_cli_$$_${RANDOM}}"

echo "Launching Claude CLI session: $SESSION_NAME" >&2

# Create iTerm2 tab with Claude CLI
osascript - "$SESSION_NAME" <<'OSA'
on run argv
  set sessionName to item 1 of argv
  tell application "iTerm2"
    activate
    tell current window
      set newTab to (create tab with default profile)
      tell current session of newTab
        set name to sessionName
        write text "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH"
        delay 0.5
        write text "/usr/local/bin/claude --dangerously-skip-permissions"
        return "Session created: " & sessionName
      end tell
    end tell
  end tell
end run
OSA

# Wait for Claude CLI to initialize
echo "Waiting 10 seconds for Claude CLI to initialize..." >&2
sleep 10

# Verify session exists
if osascript - "$SESSION_NAME" <<'OSA' | grep -q "found"; then
on run argv
  set target to item 1 of argv
  tell application "iTerm2"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if (name of s) contains target then
            return "found"
          end if
        end repeat
      end repeat
    end repeat
  end tell
  return "not found"
end run
OSA
    echo "✓ Claude CLI session ready: $SESSION_NAME" >&2
    echo "$SESSION_NAME"
else
    echo "✗ Failed to create session" >&2
    exit 1
fi
