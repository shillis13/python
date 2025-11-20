#!/bin/bash
# utils.sh - Helper functions for CLI control
# Source this file: source utils.sh
#
# Note: These utilities work with SESSION NAMES, not PIDs
# Session names are returned by launch_*_cli.sh scripts

# Wait for CLI response matching pattern
# Usage: wait_for_response <session_name> <pattern> <timeout_seconds>
wait_for_response() {
    local session="$1"
    local pattern="$2"
    local timeout="${3:-30}"
    local elapsed=0
    
    echo "Waiting for pattern: $pattern (timeout: ${timeout}s)" >&2
    
    while [ $elapsed -lt $timeout ]; do
        local screen
        screen=$(./monitor_cli.sh "$session" all 2>/dev/null)
        
        if echo "$screen" | grep -q "$pattern"; then
            echo "✓ Pattern found after ${elapsed}s" >&2
            return 0
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
        echo -n "." >&2
    done
    
    echo >&2
    echo "✗ Pattern not found within ${timeout}s" >&2
    return 1
}

# Send command and wait for response
# Usage: send_and_wait <session_name> "command" "response_pattern" [timeout]
send_and_wait() {
    local session="$1"
    local command="$2"
    local pattern="$3"
    local timeout="${4:-30}"
    
    echo "Sending: $command" >&2
    ./send_to_cli.sh "$session" "$command"
    
    wait_for_response "$session" "$pattern" "$timeout"
}

# Check if session exists
# Usage: session_exists <session_name>
session_exists() {
    local session="$1"
    ./monitor_cli.sh "$session" 1 &>/dev/null
    return $?
}

# List all CLI sessions (Claude and Codex)
# Usage: list_sessions
list_sessions() {
    osascript <<'EOF'
tell application "iTerm"
    set sessionList to {}
    repeat with aWindow in windows
        repeat with aTab in tabs of aWindow
            repeat with aSession in sessions of aTab
                set sessionName to name of aSession
                if sessionName contains "claude_cli_" or sessionName contains "codex_cli_" then
                    set end of sessionList to sessionName
                end if
            end repeat
        end repeat
    end repeat
    return sessionList
end tell
EOF
}

# Extract last response from screen
# Usage: get_last_response <session_name> [lines]
get_last_response() {
    local session="$1"
    local lines="${2:-20}"
    
    ./monitor_cli.sh "$session" "$lines"
}

# Wait for CLI to be ready for input
# Usage: wait_ready <session_name>
wait_ready() {
    local session="$1"
    wait_for_response "$session" "INSERT\|Welcome to Claude\|codex>" 30
}

echo "CLI control utilities loaded" >&2
echo "" >&2
echo "Note: These work with SESSION NAMES (from launch scripts), not PIDs" >&2
echo "" >&2
echo "Available functions:" >&2
echo "  • wait_for_response <session> <pattern> [timeout]" >&2
echo "  • send_and_wait <session> \"cmd\" <pattern> [timeout]" >&2
echo "  • session_exists <session>" >&2
echo "  • list_sessions" >&2
echo "  • get_last_response <session> [lines]" >&2
echo "  • wait_ready <session>" >&2
