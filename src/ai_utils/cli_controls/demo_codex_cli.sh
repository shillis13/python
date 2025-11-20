#!/bin/bash
# demo_codex_cli.sh - Demonstration of CLI control for Codex CLI

set -e

echo "=== Codex CLI Control Demonstration ==="
echo
echo "This demo shows controlling a Codex CLI session"
echo
echo "Press Enter to continue..."
read

# Step 1: Launch Codex CLI
echo
echo "Step 1: Launch Codex CLI session"
echo "----------------------------------"
SESSION=$(./launch_codex_cli.sh)
echo "Session identifier: $SESSION"
echo

# Step 2: Verify it's running
echo "Step 2: Verify Codex is ready"
echo "-------------------------------"
./monitor_cli.sh "$SESSION" 30
echo
echo "✓ Codex is running in iTerm2"
echo
echo "Press Enter to send first command..."
read

# Step 3: Send command
echo
echo "Step 3: Send command to Codex"
echo "-------------------------------"
./send_to_cli.sh "$SESSION" "Search for all Python files in /tmp"
echo
echo "✓ Command sent (non-blocking)"
echo "Waiting 20 seconds for Codex to process..."
sleep 20
echo

# Step 4: Monitor response
echo "Step 4: Check Codex response"
echo "-----------------------------"
./monitor_cli.sh "$SESSION" 60
echo

# Step 5: Send follow-up
echo
echo "Step 5: Send follow-up command"
echo "--------------------------------"
echo "Press Enter to continue..."
read

./send_to_cli.sh "$SESSION" "Now count how many Python files you found"
echo "Waiting for response..."
sleep 15
echo
./monitor_cli.sh "$SESSION" 40
echo

# Cleanup
echo
echo "Step 6: Cleanup"
echo "----------------"
echo "Leave Codex session open? (y/n)"
read -r KEEP
if [ "$KEEP" != "y" ]; then
    ./kill_cli.sh "$SESSION"
    echo "✓ Session closed"
else
    echo "Session remains open: $SESSION"
fi

echo
echo "=== Demo Complete ===" 
echo
echo "Key Points:"
echo "  • Codex and Claude use same control scripts"
echo "  • Only launch script differs (launch_codex_cli vs launch_claude_cli)"
echo "  • send_to_cli, monitor_cli, kill_cli work for both"
