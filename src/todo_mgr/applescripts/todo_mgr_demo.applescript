-- todo_mgr_demo.applescript
-- Sends a short demo sequence to the active Terminal tab running todo_mgr.

set demoCommands to {"home", "kanban", "list ready", "view RD1", "view todo_nested_showcase/todo_subtask_alpha"}

tell application "Terminal"
    activate
end tell

tell application "System Events"
    tell process "Terminal"
        repeat with cmd in demoCommands
            set cmdText to cmd as string
            keystroke cmdText
            key code 36 -- Return
            delay 0.35
        end repeat
    end tell
end tell
