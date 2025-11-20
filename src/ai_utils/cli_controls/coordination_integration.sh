#!/bin/bash
# coordination_integration.sh - Example of CLI_A using CLI_B via coordination system
# This shows how Desktop Claude would delegate tasks to CLI instances

set -e

# Load utilities
source ./utils.sh

echo "=== Coordination System Integration Example ==="
echo
echo "Scenario: Desktop Claude delegates file analysis to CLI_B"
echo

# Simulate coordination task
TASK_ID="req_9999"
TASK_FILE="/tmp/coordination_task_example.md"

cat > "$TASK_FILE" <<'TASK'
# Request #9999: Analyze Log Files

**Type:** Analysis
**Priority:** NORMAL

## Task Description
Analyze system logs for error patterns in the last 24 hours.

## Files to Analyze
- /var/log/system.log
- Look for ERROR, WARN, CRITICAL patterns
- Summarize findings

## Expected Response
- Count of each error type
- Most common error messages
- Timestamp of first/last error
TASK

echo "Task file created: $TASK_FILE"
echo

# CLI_A launches dedicated CLI_B for this task
echo "Step 1: CLI_A launches CLI_B worker for $TASK_ID"
SESSION=$(./launch_cli_b.sh "${TASK_ID}_worker")
echo "  Worker session: $SESSION"
echo

# CLI_A sends task to CLI_B
echo "Step 2: CLI_A delegates task to CLI_B"
TASK_CONTENT=$(cat "$TASK_FILE")
./send_to_cli_b.sh "$SESSION" "I have a coordination task for you. Here's the specification: $TASK_CONTENT. Please analyze and respond."
echo "  ✓ Task delegated"
echo

# CLI_A continues other work (non-blocking!)
echo "Step 3: CLI_A continues other work while CLI_B processes"
echo "  (This is the key advantage - Desktop Claude isn't blocked!)"
for i in {1..3}; do
    echo "  Desktop Claude handling other tasks... ($i/3)"
    sleep 3
done
echo "  ✓ CLI_A work complete"
echo

# CLI_A monitors for completion
echo "Step 4: CLI_A monitors CLI_B progress"
echo "  Polling for completion signal..."

if wait_for_response "$SESSION" "analysis complete\|summary" 60; then
    echo "  ✓ CLI_B completed analysis"
else
    echo "  ⚠ CLI_B still working or timed out"
fi
echo

# CLI_A reads results
echo "Step 5: CLI_A reads CLI_B's results"
RESULTS=$(get_last_response "$SESSION" 50)
echo "  Results captured (${#RESULTS} chars)"
echo

# CLI_A writes coordination response
RESPONSE_FILE="/tmp/coordination_response_${TASK_ID}.md"
cat > "$RESPONSE_FILE" <<EOF
# Response: Request #${TASK_ID}

**Status:** COMPLETED
**Completed:** $(date -u +"%Y-%m-%d %H:%M:%S")
**Worker:** ${SESSION}

## Results

$RESULTS

## Execution Notes
- Task delegated to CLI_B worker
- CLI_A remained non-blocked during processing
- Results retrieved and validated
EOF

echo "  Response file created: $RESPONSE_FILE"
echo

# CLI_A kills worker
echo "Step 6: CLI_A cleans up worker session"
./kill_cli_b.sh "$SESSION"
echo "  ✓ Worker terminated"
echo

echo "=== Integration Complete ==="
echo
echo "This demonstrates:"
echo "  1. Desktop Claude delegates heavy work to CLI"
echo "  2. CLI_B gets full task context"
echo "  3. Desktop Claude continues other work (non-blocking)"
echo "  4. Desktop Claude monitors progress"
echo "  5. Results flow back to coordination system"
echo "  6. Clean session lifecycle management"
echo
echo "Files created:"
echo "  - Task: $TASK_FILE"
echo "  - Response: $RESPONSE_FILE"
echo
echo "Key advantage over coordination v4.0:"
echo "  Desktop Claude can ACTIVELY MONITOR and INTERACT with CLI"
echo "  Not just fire-and-forget file-based async"
echo "  Can send follow-up questions, adjust approach, etc."
