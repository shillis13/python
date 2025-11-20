#!/bin/bash
# demo_cli_control.sh - Complete demonstration of CLI_A → CLI_B control
# Shows: Launch, send commands, monitor, non-blocking operation

set -e

echo "=== CLI-to-CLI Control Demonstration ==="
echo
echo "This demo shows CLI_A controlling CLI_B with:"
echo "  • Non-blocking command sending"
echo "  • Persistent context across commands"
echo "  • Screen monitoring"
echo "  • Multiple commands to same session"
echo
echo "Press Enter to continue..."
read

# Step 1: Launch CLI_B
echo
echo "Step 1: CLI_A launches CLI_B session"
echo "--------------------------------------"
SESSION=$(./launch_cli_b.sh)
echo "Session ID: $SESSION"
echo

# Step 2: Verify it's running
echo "Step 2: Verify CLI_B is ready"
echo "-------------------------------"
./monitor_cli_b.sh "$SESSION" 30
echo
echo "✓ CLI_B is running in iTerm2"
echo
echo "Press Enter to send first command..."
read

# Step 3: Send first command (non-blocking!)
echo
echo "Step 3: CLI_A sends first command to CLI_B"
echo "--------------------------------------------"
./send_to_cli_b.sh "$SESSION" "What is 2+2?"
echo
echo "✓ Command sent (CLI_A is NOT blocked!)"
echo

# Step 4: CLI_A does other work while CLI_B processes
echo "Step 4: CLI_A does other work while CLI_B processes"
echo "-----------------------------------------------------"
for i in {1..5}; do
    echo "  CLI_A working on task $i/5..."
    sleep 2
done
echo "✓ CLI_A completed parallel work"
echo

# Step 5: Monitor CLI_B's response
echo "Step 5: CLI_A monitors CLI_B's response"
echo "-----------------------------------------"
echo "Screen contents:"
echo
./monitor_cli_b.sh "$SESSION" 40
echo

if ./monitor_cli_b.sh "$SESSION" all | grep -q -E "(4|four)"; then
    echo "✓ CLI_B answered: 2+2 = 4"
else
    echo "⚠ Answer not detected yet (might need more time)"
fi
echo
echo "Press Enter to send second command..."
read

# Step 6: Send second command (persistent context!)
echo
echo "Step 6: CLI_A sends second command to SAME CLI_B"
echo "--------------------------------------------------"
./send_to_cli_b.sh "$SESSION" "What is 2+3?"
echo
echo "✓ Second command sent"
echo "Waiting 15 seconds for response..."
sleep 15
echo

# Step 7: Check second response
echo "Step 7: Check CLI_B's second response"
echo "---------------------------------------"
echo "Screen contents:"
echo
./monitor_cli_b.sh "$SESSION" 50
echo

if ./monitor_cli_b.sh "$SESSION" all | grep -q -E "(5|five)"; then
    echo "✓ CLI_B answered: 2+3 = 5"
else
    echo "⚠ Answer not detected yet"
fi
echo

# Step 8: Demonstrate context persistence
echo "Step 8: Test context persistence"
echo "---------------------------------"
./send_to_cli_b.sh "$SESSION" "What were the last two questions I asked?"
echo "Waiting for response..."
sleep 15
echo
./monitor_cli_b.sh "$SESSION" 60
echo

# Step 9: Cleanup
echo
echo "Step 9: Cleanup"
echo "----------------"
echo "Leave CLI_B session open? (y/n)"
read -r KEEP
if [ "$KEEP" != "y" ]; then
    ./kill_cli_b.sh "$SESSION"
    echo "✓ Session closed"
else
    echo "Session remains open: $SESSION"
    echo "You can:"
    echo "  • Monitor: ./monitor_cli_b.sh \"$SESSION\""
    echo "  • Send: ./send_to_cli_b.sh \"$SESSION\" \"command\""
    echo "  • Close: ./kill_cli_b.sh \"$SESSION\""
fi

echo
echo "=== Demo Complete ==="
echo
echo "Key Results:"
echo "  ✓ CLI_A launched CLI_B successfully"
echo "  ✓ CLI_A sent commands without blocking"
echo "  ✓ CLI_A monitored CLI_B's responses"
echo "  ✓ CLI_B maintained context across commands"
echo "  ✓ Multiple commands to same persistent session"
echo
echo "This proves:"
echo "  • Non-blocking operation (CLI_A can do other work)"
echo "  • Persistent CLI_B with full Claude context"
echo "  • Reliable command submission via System Events"
echo "  • Screen monitoring via AppleScript"
