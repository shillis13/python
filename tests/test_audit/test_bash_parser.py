# test_bash_parser.py
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "bin" / "ai"))

def test_parse_rm():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "rm -f /tmp/file.py", "description": "delete"})
    ops = parse_bash_input(preview)
    assert len(ops) == 1
    assert ops[0].action == "deleted"
    assert ops[0].path == "/tmp/file.py"
    assert ops[0].destination is None

def test_parse_mv():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "mv old.py new.py"})
    ops = parse_bash_input(preview)
    assert len(ops) == 1
    assert ops[0].action == "renamed"
    assert ops[0].path == "old.py"
    assert ops[0].destination == "new.py"

def test_parse_cp():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "cp src.py dst.py"})
    ops = parse_bash_input(preview)
    assert len(ops) == 1
    assert ops[0].action == "copied"

def test_parse_git_mv():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "git mv old.py new.py"})
    ops = parse_bash_input(preview)
    assert len(ops) == 1
    assert ops[0].action == "renamed"
    assert ops[0].path == "old.py"

def test_parse_rm_rf():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "rm -rf /tmp/dir/"})
    ops = parse_bash_input(preview)
    assert len(ops) == 1
    assert ops[0].action == "deleted"
    assert ops[0].path == "/tmp/dir/"

def test_json_decode_failure():
    from audit.bash_parser import parse_bash_input
    ops = parse_bash_input("rm -f /tmp/file.py")
    assert len(ops) == 1  # Falls back to raw string

def test_truncated_input():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "rm file.py"})
    ops = parse_bash_input(preview, input_length=9999)
    assert ops[0].truncated is True

def test_no_file_ops():
    from audit.bash_parser import parse_bash_input
    preview = json.dumps({"command": "echo hello"})
    ops = parse_bash_input(preview)
    assert len(ops) == 0

def test_empty_input():
    from audit.bash_parser import parse_bash_input
    assert parse_bash_input("") == []
    assert parse_bash_input("{}") == []
