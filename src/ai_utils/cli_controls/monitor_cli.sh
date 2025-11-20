#!/usr/bin/env bash
set -euo pipefail

# Legacy shim for monitor_cli.sh -> monitor.sh cli

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <session_name> [lines_to_show]" >&2
  exit 1
fi

SESSION_NAME="$1"
LINES="${2:-50}"
MONITOR_SCRIPT="$HOME/Documents/AI/ai_root/ai_general/scripts/monitor.sh"

if [[ ! -x "$MONITOR_SCRIPT" ]]; then
  echo "ERROR: monitor.sh not found at $MONITOR_SCRIPT" >&2
  exit 1
fi

exec "$MONITOR_SCRIPT" cli "$SESSION_NAME" --lines "$LINES"
