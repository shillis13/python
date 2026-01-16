#!/usr/bin/env python3
"""
lctl_mgr.py - Manage macOS background services (launchd)

macOS runs background tasks through "launchd". This tool helps you:
- See what's running
- Start/stop services  
- Create new scheduled tasks
- Debug failing services

Location: ~/bin/ai/cli/lctl_mgr.py
Version: 1.0.0
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import gettempdir

# =============================================================================
# Constants
# =============================================================================

USER_SERVICES = Path.home() / "Library/LaunchAgents"
SYSTEM_SERVICES = Path("/Library/LaunchAgents")
INDEX_CACHE = Path(gettempdir()) / f"lctl_mgr_index_{os.getuid()}.json"

HELP_VERBOSE = """
WHAT IS LAUNCHD?
================

launchd is how macOS runs background tasks. It's like:
- Windows Task Scheduler
- Linux systemd/cron
- "Apps that run without you clicking them"

TWO KEY FILES
-------------

1. Config files (.plist) - XML files that say:
   - What script/program to run
   - When to run it (every 10 min, daily at 9am, when a file changes)
   - Where to log output
   
   Location: ~/Library/LaunchAgents/com.yourname.taskname.plist

2. The service itself - The running process managed by launchd

COMMON STATES
-------------

Loaded + Running (has PID): Service is active right now
Loaded + Not running (no PID): Waiting for trigger (time, file change, etc)
Not loaded: launchd doesn't know about it (plist exists but inactive)
Error 127: Script path in config is wrong

TYPICAL WORKFLOW
----------------

1. Create config: lctl_mgr create mytask --script /path/to/script.sh --interval 600
2. Activate it:    lctl_mgr load mytask  
3. Check status:   lctl_mgr list
4. View logs:      Check the log path shown in 'lctl_mgr show mytask'

WHY USE THIS INSTEAD OF CRON?
-----------------------------

- Runs with your user permissions (Full Disk Access works)
- Better logging
- Can trigger on file changes, not just time
- Survives sleep/wake properly
- macOS native (cron is legacy)
"""

HELP_EXAMPLES = """
EXAMPLES
========

See what's running:
  lctl_mgr list                    # All your services
  lctl_mgr list -f pulse           # Filter by name
  lctl_mgr list -a                 # Include Apple services

Check a specific service (use index from list):
  lctl_mgr status 1                # By index
  lctl_mgr status com.user.mytask  # By full name

View the config file:
  lctl_mgr show 1

Start/stop services:
  lctl_mgr start 1
  lctl_mgr stop 1
  lctl_mgr restart 1

Activate/deactivate a config:
  lctl_mgr load 1                  # Tell launchd about it
  lctl_mgr unload 1                # Remove from launchd

Create a new scheduled task:
  lctl_mgr create mytask -s /path/to/script.sh --interval 600   # Every 10 min
  lctl_mgr create mytask -s /path/to/script.sh --hourly         # Every hour
  lctl_mgr create mytask -s /path/to/script.sh --daily 9 0      # Daily at 9am

List config files on disk:
  lctl_mgr configs

Generate shell completions:
  lctl_mgr --completions bash >> ~/.bashrc
  lctl_mgr --completions zsh >> ~/.zshrc
"""

# =============================================================================
# Helpers
# =============================================================================

def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Run command, return (code, stdout, stderr)."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def find_config(label: str) -> Path | None:
    """Find config file by label."""
    if label.endswith('.plist'):
        p = Path(label).expanduser()
        return p if p.exists() else None
    
    for d in [USER_SERVICES, SYSTEM_SERVICES]:
        p = d / f"{label}.plist"
        if p.exists():
            return p
    return None


def load_index() -> dict:
    """Load cached index mapping."""
    if INDEX_CACHE.exists():
        try:
            return json.loads(INDEX_CACHE.read_text())
        except:
            pass
    return {}


def save_index(mapping: dict):
    """Save index mapping to cache."""
    INDEX_CACHE.write_text(json.dumps(mapping))


def resolve_label(ref: str) -> str:
    """Resolve index number or label to full label."""
    if ref.isdigit():
        idx = load_index()
        if ref in idx:
            return idx[ref]
        print(f"Index {ref} not found. Run 'lctl_mgr list' first.")
        sys.exit(1)
    return ref


# =============================================================================
# Commands
# =============================================================================

def cmd_list(args):
    """List running services."""
    code, stdout, _ = run_cmd(["launchctl", "list"])
    
    lines = stdout.strip().split('\n')[1:]  # Skip header
    
    if not args.all:
        lines = [l for l in lines if 'com.apple' not in l]
    
    if args.filter:
        lines = [l for l in lines if args.filter.lower() in l.lower()]
    
    # Sort by label
    lines.sort(key=lambda x: x.split('\t')[-1] if '\t' in x else x)
    
    # Build index
    idx_map = {}
    
    print(f"{'#':<4} {'PID':<8} {'Status':<10} Label")
    print("-" * 70)
    
    for i, line in enumerate(lines, 1):
        parts = line.split('\t')
        if len(parts) >= 3:
            pid, status, label = parts[0], parts[1], parts[2]
            
            idx_map[str(i)] = label
            
            pid_str = pid if pid != '-' else '-'
            if status == '-' or status == '0':
                status_str = 'ok'
            else:
                status_str = f'ERR:{status}'
            
            print(f"{i:<4} {pid_str:<8} {status_str:<10} {label}")
    
    save_index(idx_map)
    print(f"\nTotal: {len(lines)} services")


def cmd_status(args):
    """Show service status."""
    label = resolve_label(args.ref)
    
    code, stdout, _ = run_cmd(["launchctl", "list"])
    
    found = None
    for line in stdout.split('\n'):
        if label in line:
            found = line
            break
    
    if not found:
        print(f"'{label}' is not loaded (inactive)")
        cfg = find_config(label)
        if cfg:
            print(f"Config exists: {cfg}")
            print("Run 'lctl_mgr load' to activate")
        return 1
    
    parts = found.split('\t')
    pid, status = parts[0], parts[1]
    
    print(f"Service: {label}")
    print(f"PID:     {pid if pid != '-' else 'Not running (waiting for trigger)'}")
    
    if status == '-' or status == '0':
        print(f"Status:  OK")
    else:
        print(f"Status:  ERROR (code {status})")
        if status == '127':
            print("         → Script path not found. Check config with 'show'")
    
    cfg = find_config(label)
    if cfg:
        print(f"Config:  {cfg}")


def cmd_show(args):
    """Show config file contents."""
    label = resolve_label(args.ref)
    cfg = find_config(label)
    
    if not cfg:
        print(f"No config found for '{label}'")
        return 1
    
    print(f"=== {cfg} ===\n")
    print(cfg.read_text())


def cmd_load(args):
    """Activate a service config."""
    label = resolve_label(args.ref)
    cfg = find_config(label)
    
    if not cfg:
        print(f"No config found for '{label}'")
        return 1
    
    code, _, err = run_cmd(["launchctl", "load", str(cfg)])
    if code == 0:
        print(f"Loaded: {label}")
    else:
        print(f"Error: {err}")
    return code


def cmd_unload(args):
    """Deactivate a service."""
    label = resolve_label(args.ref)
    cfg = find_config(label)
    
    if not cfg:
        print(f"No config found for '{label}'")
        return 1
    
    code, _, err = run_cmd(["launchctl", "unload", str(cfg)])
    if code == 0:
        print(f"Unloaded: {label}")
    else:
        print(f"Error: {err}")
    return code


def cmd_start(args):
    """Start a service now."""
    label = resolve_label(args.ref)
    code, _, err = run_cmd(["launchctl", "start", label])
    if code == 0:
        print(f"Started: {label}")
    else:
        print(f"Error: {err}")
    return code


def cmd_stop(args):
    """Stop a running service."""
    label = resolve_label(args.ref)
    code, _, err = run_cmd(["launchctl", "stop", label])
    if code == 0:
        print(f"Stopped: {label}")
    else:
        print(f"Error: {err}")
    return code


def cmd_restart(args):
    """Restart a service."""
    label = resolve_label(args.ref)
    run_cmd(["launchctl", "stop", label])
    code, _, err = run_cmd(["launchctl", "start", label])
    if code == 0:
        print(f"Restarted: {label}")
    else:
        print(f"Error: {err}")
    return code


def cmd_configs(args):
    """List config files on disk."""
    print("YOUR CONFIGS:")
    print(f"  {USER_SERVICES}/\n")
    
    if USER_SERVICES.exists():
        for p in sorted(USER_SERVICES.glob("*.plist")):
            print(f"    {p.name}")
    else:
        print("    (directory doesn't exist)")
    
    print(f"\nSYSTEM CONFIGS:")
    print(f"  {SYSTEM_SERVICES}/\n")
    
    if SYSTEM_SERVICES.exists():
        for p in sorted(SYSTEM_SERVICES.glob("*.plist")):
            if 'com.apple' not in p.name or args.all:
                print(f"    {p.name}")


def cmd_create(args):
    """Create a new service config."""
    user = os.environ.get('USER', 'user')
    label = f"com.{user}.{args.name}"
    cfg_path = USER_SERVICES / f"{label}.plist"
    
    if cfg_path.exists() and not args.force:
        print(f"Config already exists: {cfg_path}")
        print("Use --force to overwrite")
        return 1
    
    # Build schedule
    schedule = ""
    if args.interval:
        schedule = f"""
    <key>StartInterval</key>
    <integer>{args.interval}</integer>"""
    elif args.hourly:
        schedule = """
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>0</integer>
    </dict>"""
    elif args.daily:
        h, m = args.daily
        schedule = f"""
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{h}</integer>
        <key>Minute</key>
        <integer>{m}</integer>
    </dict>"""
    
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{args.script}</string>
    </array>
{schedule}
    
    <key>StandardOutPath</key>
    <string>/tmp/{args.name}.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/{args.name}.log</string>
    
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    
    USER_SERVICES.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(content)
    
    print(f"Created: {cfg_path}")
    print(f"Label:   {label}")
    print(f"Log:     /tmp/{args.name}.log")
    print(f"\nTo activate: lctl_mgr load {label}")


def print_completions(shell: str):
    """Print shell completion script."""
    if shell == 'bash':
        print("""
_lctl_mgr_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local cmd="${COMP_WORDS[1]}"
    
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=($(compgen -W "list status show load unload start stop restart configs create" -- "$cur"))
    elif [[ $COMP_CWORD -eq 2 ]]; then
        case "$cmd" in
            status|show|load|unload|start|stop|restart)
                local services=$(launchctl list 2>/dev/null | tail -n +2 | awk '{print $3}' | grep -v com.apple)
                COMPREPLY=($(compgen -W "$services" -- "$cur"))
                ;;
        esac
    fi
}
complete -F _lctl_mgr_completions lctl_mgr
""")
    elif shell == 'zsh':
        print("""
#compdef lctl_mgr

_lctl_mgr() {
    local -a commands
    commands=(
        'list:List running services'
        'status:Show service status'
        'show:Show config file'
        'load:Activate a service'
        'unload:Deactivate a service'
        'start:Start service now'
        'stop:Stop running service'
        'restart:Restart service'
        'configs:List config files'
        'create:Create new service'
    )
    
    _arguments -C \\
        '1: :->command' \\
        '2: :->args'
    
    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[2] in
                status|show|load|unload|start|stop|restart)
                    local -a services
                    services=(${(f)"$(launchctl list 2>/dev/null | tail -n +2 | awk '{print $3}' | grep -v com.apple)"})
                    _describe 'service' services
                    ;;
            esac
            ;;
    esac
}

_lctl_mgr
""")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog='lctl_mgr',
        description='Manage macOS background services',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Use --help-verbose for concepts, --help-examples for usage"
    )
    
    parser.add_argument('--help-verbose', action='store_true',
                        help='Explain what launchd is and how it works')
    parser.add_argument('--help-examples', action='store_true',
                        help='Show example commands')
    parser.add_argument('--completions', choices=['bash', 'zsh'],
                        help='Print shell completion script')
    
    sub = parser.add_subparsers(dest='cmd', title='commands')
    
    # list
    p = sub.add_parser('list', help='List running services')
    p.add_argument('-a', '--all', action='store_true', help='Include Apple services')
    p.add_argument('-f', '--filter', help='Filter by name')
    p.set_defaults(func=cmd_list)
    
    # status
    p = sub.add_parser('status', help='Show service status')
    p.add_argument('ref', help='Index # from list, or full service name')
    p.set_defaults(func=cmd_status)
    
    # show
    p = sub.add_parser('show', help='Show config file contents')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_show)
    
    # load
    p = sub.add_parser('load', help='Activate a service (tell macOS to manage it)')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_load)
    
    # unload
    p = sub.add_parser('unload', help='Deactivate a service (macOS stops managing it)')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_unload)
    
    # start
    p = sub.add_parser('start', help='Run the service right now')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_start)
    
    # stop
    p = sub.add_parser('stop', help='Stop the service if running')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_stop)
    
    # restart
    p = sub.add_parser('restart', help='Stop then start the service')
    p.add_argument('ref', help='Index # or service name')
    p.set_defaults(func=cmd_restart)
    
    # configs
    p = sub.add_parser('configs', help='List config files on disk (not just running services)')
    p.add_argument('-a', '--all', action='store_true', help='Include Apple configs')
    p.set_defaults(func=cmd_configs)
    
    # create
    p = sub.add_parser('create', help='Create a new scheduled task')
    p.add_argument('name', help='Short name (becomes com.youruser.name)')
    p.add_argument('-s', '--script', required=True, help='Script to run')
    p.add_argument('--interval', type=int, help='Run every N seconds')
    p.add_argument('--hourly', action='store_true', help='Run every hour')
    p.add_argument('--daily', nargs=2, type=int, metavar=('H', 'M'), help='Run daily at H:M')
    p.add_argument('-f', '--force', action='store_true', help='Overwrite existing')
    p.set_defaults(func=cmd_create)
    
    args = parser.parse_args()
    
    if args.help_verbose:
        print(HELP_VERBOSE)
        return 0
    
    if args.help_examples:
        print(HELP_EXAMPLES)
        return 0
    
    if args.completions:
        print_completions(args.completions)
        return 0
    
    if not args.cmd:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main() or 0)
