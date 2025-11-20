#!/bin/bash
# index.sh - Navigation hub for CLI control system
# Run this for quick access to all functions

cat <<'EOF'
╔════════════════════════════════════════════════════════════╗
║           CLI-to-CLI Control System                        ║
║         AppleScript + System Events Solution               ║
╚════════════════════════════════════════════════════════════╝

📁 LOCATION: /tmp/cli_control/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 QUICK START:

  1. Run demo:           ./demo_cli_control.sh
  2. Try integration:    ./coordination_integration.sh
  3. Read docs:          less README.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 CORE SCRIPTS:

  Launch CLI_B:         ./launch_cli_b.sh [name]
  Send command:         ./send_to_cli_b.sh <session> "cmd"
  Monitor screen:       ./monitor_cli_b.sh <session> [lines]
  Kill session:         ./kill_cli_b.sh <session>
  
  Utilities:            source ./utils.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 DOCUMENTATION:

  Complete guide:       README.md
  Quick reference:      QUICK_REFERENCE.md
  Solution summary:     SOLUTION_SUMMARY.md
  This index:           index.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 EXAMPLES:

  Basic usage:
    session=$(./launch_cli_b.sh)
    ./send_to_cli_b.sh "$session" "What is 2+2?"
    ./monitor_cli_b.sh "$session"
    ./kill_cli_b.sh "$session"

  With utilities:
    source ./utils.sh
    session=$(./launch_cli_b.sh)
    send_and_wait "$session" "Analyze logs" "complete" 60
    results=$(get_last_response "$session")
    ./kill_cli_b.sh "$session"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 KEY FEATURES:

  ✓ Non-blocking operation (CLI_A never waits)
  ✓ Persistent context (CLI_B remembers across commands)
  ✓ Full monitoring (read entire screen anytime)
  ✓ Reliable submission (System Events keyboard works)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔬 THE DISCOVERY:

  Problem: Claude CLI TUI requires GUI keyboard events
  Solution: AppleScript System Events 'keystroke'
  
  Failed: stdin, pipes, coprocess, Desktop Commander
  Works:  System Events (GUI-level keyboard)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️  REQUIREMENTS:

  • macOS (System Events is macOS-specific)
  • iTerm2 (scripts target iTerm2's AppleScript API)
  • Claude CLI installed at /usr/local/bin/claude

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

# Offer interactive menu
echo "What would you like to do?"
echo
echo "1) Run demo"
echo "2) Run coordination integration example"
echo "3) Launch a CLI_B session (manual control)"
echo "4) List all active CLI_B sessions"
echo "5) View README"
echo "6) View quick reference"
echo "7) Exit"
echo
read -p "Choice (1-7): " choice

case $choice in
    1)
        echo
        ./demo_cli_control.sh
        ;;
    2)
        echo
        ./coordination_integration.sh
        ;;
    3)
        echo
        session=$(./launch_cli_b.sh)
        echo
        echo "CLI_B session launched: $session"
        echo
        echo "Try:"
        echo "  ./send_to_cli_b.sh \"$session\" \"What is 2+2?\""
        echo "  ./monitor_cli_b.sh \"$session\""
        echo "  ./kill_cli_b.sh \"$session\""
        ;;
    4)
        echo
        echo "Active CLI_B sessions:"
        source ./utils.sh
        list_sessions
        ;;
    5)
        less README.md
        ;;
    6)
        less QUICK_REFERENCE.md
        ;;
    7)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
