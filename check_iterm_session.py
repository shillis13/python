#!/usr/bin/env python3
"""
Check iTerm2 session output
Usage: python3 check_session.py <session_id>
"""

import iterm2
import asyncio
import sys


async def check_session(connection, session_id):
    """Read current screen contents of a specific session."""
    app = await iterm2.async_get_app(connection)
    
    # Find the session by ID
    target_session = None
    for window in app.terminal_windows:
        for tab in window.tabs:
            for session in tab.sessions:
                # iTerm2 uses session.session_id, not async_get_variable
                if session.session_id == session_id:
                    target_session = session
                    break
            if target_session:
                break
        if target_session:
            break
    
    if not target_session:
        print(f"ERROR: Session {session_id} not found")
        print("\nAvailable sessions:")
        for window in app.terminal_windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    name = await session.async_get_variable("name") or "unnamed"
                    print(f"  - {session.session_id} ({name})")
        return
    
    # Get screen contents
    print(f"Session: {session_id}")
    name = await target_session.async_get_variable("name") or "unnamed"
    print(f"Name: {name}")
    print("=" * 70)
    
    contents = await target_session.async_get_screen_contents()
    
    # Print visible lines
    for line in contents.line:
        text = "".join([s.string for s in line.string_at])
        print(text)  # Print even empty lines to preserve layout
    
    print("=" * 70)


async def main(connection):
    if len(sys.argv) < 2:
        print("Usage: python3 check_session.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    await check_session(connection, session_id)


if __name__ == "__main__":
    try:
        iterm2.run_until_complete(main)
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nMake sure:")
        print("1. iTerm2 is running")
        print("2. Python API is enabled (Prefs > General > Magic > Enable Python API)")
        sys.exit(1)
