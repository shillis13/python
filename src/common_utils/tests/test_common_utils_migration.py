#!/usr/bin/env python3
"""
Automated test suite for common_utils consolidation migration.

Validates that all migrated consumers correctly use common_utils.Colors,
common_utils.lib_fileIO, and file_utils.lib_fileInput.

Usage:
    python3 test_common_utils_migration.py
"""

import os
import re
import subprocess
import sys

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..")


def run_cmd(cmd):
    """Run a shell command from src dir, return (stdout+stderr, returncode)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=SRC_DIR, timeout=30,
    )
    return result.stdout + result.stderr, result.returncode


def run_tests(test_groups):
    """Run all test groups, print results, return exit code."""
    total = 0
    passed = 0
    failed = 0
    failures = []

    for group_name, tests in test_groups:
        print(f"\n{'=' * 60}")
        print(f"  {group_name}")
        print(f"{'=' * 60}")

        for t in tests:
            total += 1
            cmd = t["cmd"]
            desc = t["desc"]
            check = t["check"]

            output, rc = run_cmd(cmd)

            try:
                ok = check(output)
            except TypeError:
                ok = check(output, rc)

            if ok:
                passed += 1
                print(f"  PASS  {desc}")
                print(f"        $ {cmd}")
            else:
                failed += 1
                print(f"  FAIL  {desc}")
                print(f"        $ {cmd}")
                lines = output.strip().splitlines()
                if lines:
                    for line in lines[:5]:
                        print(f"        > {line[:120]}")
                    if len(lines) > 5:
                        print(f"        > ... ({len(lines) - 5} more lines)")
                else:
                    print(f"        > (no output)")
                print(f"        exit code: {rc}")
                failures.append(desc)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failures:
        print(f"\n  Failed tests:")
        for f in failures:
            print(f"    - {f}")

    return 1 if failed else 0


# ============================================================
# Test groups
# ============================================================

def test_common_utils_core():
    """Verify common_utils Colors, colorize_string, and lib_fileIO."""
    return [
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import Colors; "
                "attrs = ['RESET','BOLD','DIM','RED','GREEN','YELLOW','BLUE',"
                "'MAGENTA','CYAN','WHITE','GRAY','GREY','BG_RED','BG_BLUE']; "
                "[getattr(Colors, a) for a in attrs]; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "Colors class has all expected attributes",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import Colors; "
                "Colors.enable(); "
                "r = Colors.colorize('test', Colors.RED); "
                r"assert '\033[31m' in r and '\033[0m' in r; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "Colors.colorize emits ANSI codes when enabled",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import Colors; "
                "Colors.disable(); "
                "assert Colors.colorize('test', Colors.RED) == 'test'; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "Colors.colorize returns plain text when disabled",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import colorize_string, Colors; "
                "Colors.enable(); "
                "r = colorize_string('x', fore_color='yellow', style='bright'); "
                r"assert '\033[1m' in r and '\033[33m' in r; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "colorize_string backward compat: style=bright maps to BOLD",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import colorize_string, Colors; "
                "Colors.enable(); "
                "r = colorize_string('x', fore_color='gray'); "
                r"assert '\033[90m' in r; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "colorize_string: fore_color=gray maps to GRAY (\\033[90m)",
        },
        {
            "cmd": (
                'NO_COLOR=1 python3 -c "'
                "from common_utils.lib_outputColors import Colors; "
                "assert not Colors.enabled(); "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "NO_COLOR env var disables colors",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_fileIO import load_yaml, save_yaml, load_json, save_json; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "lib_fileIO imports successfully",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_fileIO import load_yaml; "
                "r = load_yaml('/nonexistent/path.yml', default=42); "
                "assert r == 42; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "load_yaml returns default on missing file",
        },
        {
            "cmd": (
                'python3 -c "'
                "from common_utils.lib_outputColors import print_colored; "
                "assert callable(print_colored); "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "print_colored exists and is callable",
        },
    ]


def test_dir_struct_discovery():
    """Verify dir_struct_discovery uses Colors from common_utils."""
    ANSI_RE = re.compile(r"\033\[")
    return [
        {
            "cmd": "script -q /dev/null bash -c 'python3 -m metadata_utils.dir_struct_discovery --help-examples 2>/dev/null'",
            "check": lambda out, _re=ANSI_RE: bool(_re.search(out)),
            "desc": "--help-examples contains ANSI color codes in TTY mode",
        },
        {
            "cmd": "NO_COLOR=1 python3 -m metadata_utils.dir_struct_discovery --help-examples 2>/dev/null",
            "check": lambda out, _re=ANSI_RE: not _re.search(out) and len(out.strip()) > 0,
            "desc": "--help-examples suppresses ANSI codes when NO_COLOR=1",
        },
        {
            "cmd": "python3 -m metadata_utils.dir_struct_discovery --help 2>/dev/null; echo EXIT_CODE:$?",
            "check": lambda out: "EXIT_CODE:0" in out,
            "desc": "--help exits with code 0",
        },
        {
            "cmd": "python3 -m metadata_utils.dir_struct_discovery common_utils --depth 0 2>/dev/null",
            "check": lambda out: "Total Files:" in out or "Total Directories:" in out,
            "desc": "Scanning common_utils/ --depth 0 produces statistics output",
        },
    ]


def test_gdir():
    """Verify gdir uses Colors from common_utils."""
    return [
        {
            "cmd": 'python3 -c "from gdir.cli import Colors; assert Colors.RED == \'\\033[31m\'"',
            "check": lambda out: "Traceback" not in out,
            "desc": "gdir.cli imports Colors with correct RED value",
        },
        {
            "cmd": 'python3 -c "from gdir.helptext import Colors; print(Colors.BOLD)"',
            "check": lambda out: "\033[1m" in out and "Traceback" not in out,
            "desc": "gdir.helptext imports Colors and BOLD resolves correctly",
        },
        {
            "cmd": "python3 -m gdir.cli help",
            "check": lambda out: "Traceback" not in out,
            "desc": "gdir help command runs without import errors",
        },
    ]


def test_todo_mgr():
    """Verify todo_mgr uses Colors from common_utils."""
    # todo_mgr is pip-installed as a package, so dotted import conflicts.
    # Use grep to verify the source file imports from common_utils, then run it directly.
    return [
        {
            "cmd": "grep -c 'from common_utils.lib_outputColors import Colors' todo_mgr/todo_mgr.py",
            "check": lambda out: out.strip() == "1",
            "desc": "todo_mgr.py imports Colors from common_utils (source check)",
        },
        {
            "cmd": "grep -c 'class Colors' todo_mgr/todo_mgr.py",
            "check": lambda out: out.strip() == "0",
            "desc": "todo_mgr.py has no local Colors class definition",
        },
        {
            "cmd": 'python3 -c "from common_utils.lib_outputColors import Colors; assert hasattr(Colors, \'GRAY\'); print(\'OK\')"',
            "check": lambda out: "OK" in out,
            "desc": "Colors has GRAY alias (common_utils addition)",
        },
        {
            "cmd": "python3 todo_mgr/todo_mgr.py --help",
            "check": lambda out: "usage" in out.lower() or "todo" in out.lower(),
            "desc": "todo_mgr --help runs without error",
        },
    ]


def test_pygit_yaml_utils():
    """Verify pygit and yaml_utils use Colors from common_utils."""
    return [
        {
            "cmd": 'python3 -c "from repo_tools.pygit import colour_text; print(colour_text(\'hello\', \'red\', False))"',
            "check": lambda out: out.strip() == "hello",
            "desc": "colour_text returns plain text when disabled",
        },
        {
            "cmd": (
                'python3 -c "'
                "from repo_tools.pygit import colour_text; "
                "from common_utils.lib_outputColors import Colors; "
                "result = colour_text('hello', 'red', True); "
                r"assert '\033[31m' in result; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "colour_text uses Colors.RED escape code",
        },
        {
            "cmd": (
                'python3 -c "'
                "from yaml_utils.yaml_shell import Fore, Style; "
                r"assert Fore.CYAN == '\033[36m'; "
                r"assert Style.BRIGHT == '\033[1m'; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "yaml_shell Fore/Style aliases map to Colors",
        },
        {
            "cmd": (
                'python3 -c "'
                "from yaml_utils.yaml_tree_printer import Fore, Style; "
                r"assert Style.RESET_ALL == '\033[0m'; "
                "print('OK')"
                '"'
            ),
            "check": lambda out: "OK" in out,
            "desc": "yaml_tree_printer RESET_ALL maps to Colors.RESET",
        },
        {
            "cmd": "python3 -m repo_tools.pygit --help",
            "check": lambda out: "usage" in out.lower() or "pygit" in out.lower(),
            "desc": "pygit --help runs without import error",
        },
    ]


def test_file_utils():
    """Verify file_utils modules use common_utils and lib_fileInput."""
    return [
        {
            "cmd": "python3 -m file_utils.fsActions --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "fsActions loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.fsFormat --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "fsFormat loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.treePrint --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "treePrint loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.renameFiles --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "renameFiles loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.fsFind --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "fsFind loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.fsFilters --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "fsFilters loads without import error",
        },
        {
            "cmd": "python3 -m file_utils.fsStats --help",
            "check": lambda out: "Traceback" not in out,
            "desc": "fsStats loads without import error",
        },
        {
            "cmd": 'python3 -c "from file_utils.lib_fileInput import get_file_paths_from_input; print(\'OK\')"',
            "check": lambda out: "OK" in out,
            "desc": "lib_fileInput get_file_paths_from_input importable",
        },
        {
            "cmd": 'python3 -c "from file_utils.fsActions import colorize_string; assert callable(colorize_string)"',
            "check": lambda out: "Traceback" not in out,
            "desc": "colorize_string imported through common_utils chain in fsActions",
        },
    ]


def main():
    groups = [
        ("common_utils core", test_common_utils_core()),
        ("metadata_utils/dir_struct_discovery", test_dir_struct_discovery()),
        ("gdir", test_gdir()),
        ("todo_mgr", test_todo_mgr()),
        ("repo_tools/pygit + yaml_utils", test_pygit_yaml_utils()),
        ("file_utils", test_file_utils()),
    ]
    sys.exit(run_tests(groups))


if __name__ == "__main__":
    main()
