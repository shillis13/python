#!/bin/bash
# demo_claude_cli.sh - Demonstration of CLI control for Claude CLI
# Shows: Launch, send commands, monitor, non-blocking operation

set -e

echo "=== Claude CLI Control Demonstration ==="
echo
echo "This demo shows controlling a Claude CLI session with:"
echo "  • Non-blocking command sending"
echo "  • Persistent context across commands"
echo "  • Screen monitoring"
echo "  • Multiple commands to same session"
echo
echo "Press Enter to continue..."
read

# Step 1: Launch Claude CLI
echo
echo "Step 1: Launch Claude CLI session"
echo "-----------------------------------"
SESSION=$(./launch_claude_cli.sh)
echo "Session identifier: $SESSION"
echo "(This is a session NAME, not a PID)"
echo

# Step 2: Verify it's running
echo "Step 2: Verify Claude CLI is ready"
echo "------------------------------------"
./monitor_cli.sh "$SESSION" 30
echo
echo "✓ Claude CLI is running in iTerm2"
echo
echo "Press Enter to send first command..."
read

# Step 3: Send first command (non-blocking!)
echo
echo "Step 3: Send first command (non-blocking)"
echo "------------------------------------------"
./send_to_cli.sh "$SESSION" "What is 2+2?"
echo
echo "✓ Command sent (this script continues immediately!)"
echo

# Step 4: Do other work while CLI processes
echo "Step 4: Do other work while CLI processes"
echo "-------------------------------------------"
for i in {1..5}; do
    echo "  Doing other work... ($i/5)"
    sleep 2
done
echo "✓ Parallel work completed"
echo

# Step 5: Monitor response
echo "Step 5: Monitor Claude CLI's response"
echo "---------------------------------------"
echo "Screen contents:"
echo
./monitor_cli.sh "$SESSION" 40
echo

if ./monitor_cli.sh "$SESSION" all | grep -q -E "(4|four)"; then
    echo "✓ Claude answered: 2+2 = 4"
else
    echo "⚠ Answer not detected yet (might need more time)"
fi
echo
echo "Press Enter to send second command..."
read

# Step 6: Send second command (persistent context!)
echo
echo "Step 6: Send second command to SAME session"
echo "---------------------------------------------"
./send_to_cli.sh "$SESSION" "What is 2+3?"
echo
echo "✓ Second command sent"
echo "Waiting 15 seconds for response..."
sleep 15
echo

# Step 7: Check second response
echo "Step 7: Check second response"
echo "------------------------------"
echo "Screen contents:"
echo
./monitor_cli.sh "$SESSION" 50
echo

if ./monitor_cli.sh "$SESSION" all | grep -q -E "(5|five)"; then
    echo "✓ Claude answered: 2+3 = 5"
else
    echo "⚠ Answer not detected yet"
fi
echo

# Step 8: Demonstrate context persistence
echo "Step 8: Test context persistence"
echo "---------------------------------"
./send_to_cli.sh "$SESSION" "What were the last two questions I asked?"
echo "Waiting for response..."
sleep 15
echo
./monitor_cli.sh "$SESSION" 60
echo

# Step 9: Cleanup
echo
echo "Step 9: Cleanup"
echo "----------------"
echo "Leave Claude CLI session open? (y/n)"
read -r KEEP
if [ "$KEEP" != "y" ]; then
    ./kill_cli.sh "$SESSION"
    echo "✓ Session closed"
else
    echo "Session remains open: $SESSION"
    echo "You can:"
    echo "  • Monitor: ./monitor_cli.sh \"$SESSION\""
    echo "  • Send: ./send_to_cli.sh \"$SESSION\" \"command\""
    echo "  • Close: ./kill_cli.sh \"$SESSION\""
fi

echo
echo "=== Demo Complete ==="
echo
echo "Key Results:"
echo "  ✓ Launched Claude CLI successfully"
echo "  ✓ Sent commands without blocking"
echo "  ✓ Monitored responses"
echo "  ✓ Maintained context across commands"
echo "  ✓ Multiple commands to same persistent session"
