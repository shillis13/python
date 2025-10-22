import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

import file_utils.fsFilters as fsFilters


def test_gitignore_stacked_rules_favour_deeper_patterns(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".gitignore").write_text("*.log\nimportant/\n")

    nested = repo / "nested"
    nested.mkdir()
    (nested / ".gitignore").write_text("!keep.log\n!important/\n")

    keep_log = nested / "keep.log"
    keep_log.write_text("keep")
    drop_log = nested / "drop.log"
    drop_log.write_text("drop")
    important_dir = nested / "important"
    important_dir.mkdir()

    git_filter = fsFilters.GitIgnoreFilter([repo])

    assert git_filter.should_ignore(drop_log, nested) is True
    assert git_filter.should_ignore(keep_log, nested) is False
    assert git_filter.should_ignore(important_dir, nested) is False


def test_file_system_filter_reports_active_criteria():
    fs_filter = fsFilters.FileSystemFilter()

    assert fs_filter.has_file_criteria() is False
    assert fs_filter.has_dir_criteria() is False

    fs_filter.add_file_pattern("*.py")
    fs_filter.add_dir_pattern("build*")

    assert fs_filter.has_file_criteria() is True
    assert fs_filter.has_dir_criteria() is True
