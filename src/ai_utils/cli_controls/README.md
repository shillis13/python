# CLI Controls Script Suite

This directory hosts the automation layer that lets a controller CLI ("CLI_A") launch, direct, and observe auxiliary CLI instances ("CLI_B", Claude CLI, Codex CLI). All scripts target macOS+iTerm2 and drive sessions through AppleScript plus System Events keystrokes.

## Scripts
- `index.sh` – Interactive entry point that highlights the platform, shows docs, and lets operators run demos or launch sessions quickly.
- `coordination_integration.sh` – Sample workflow where a coordinator hands off a task file to CLI_B, supervises progress, and aggregates the response.
- `demo_cli_control.sh` – Guided tour of CLI_A→CLI_B control: launch, non-blocking command sends, monitoring, and cleanup.
- `demo_claude_cli.sh` / `demo_codex_cli.sh` – Targeted demos that prove the control layer against Claude and Codex CLIs respectively.
- `launch_cli_b.sh`, `launch_claude_cli.sh`, `launch_codex_cli.sh` – Session launchers that spin up named iTerm2 tabs, prime their environments, and return session identifiers.
- `send_to_cli_b.sh` / `send_to_cli.sh` – Keyboard-driving senders that locate a named session and dispatch a command without blocking CLI_A.
- `monitor_cli_b.sh` / `monitor_cli.sh` – Screen scraping helpers that capture the visible buffer (all or tail N lines) for auditing or parsing.
- `kill_cli_b.sh` / `kill_cli.sh` – Gracefully close matching sessions when a run completes or needs to be aborted.
- `utils.sh` – Shared helpers (e.g., `send_and_wait`, `wait_for_response`, session listing) that higher-level scripts source.

## Documentation
Architecture, message flow, and detailed behavior live in `~/Documents/AI/ai_root/ai_comms/docs/cli_controls/cli_controls_architecture_v1.yml`. Use that document alongside the QUICK_REFERENCE and SOLUTION_SUMMARY files now located in the same folder for deeper design context and operational guardrails.
