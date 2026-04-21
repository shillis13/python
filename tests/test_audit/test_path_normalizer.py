# test_path_normalizer.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "bin" / "ai"))

def test_build_aliases_existing_file():
    from audit.lib_path_normalizer import build_path_aliases
    # Use a file we know exists
    f = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    aliases = build_path_aliases(f)
    assert aliases.absolute == f
    assert aliases.basename == "lib_audit.py"
    assert aliases.repo_relative is not None  # Should be in a git repo

def test_build_aliases_missing_file():
    from audit.lib_path_normalizer import build_path_aliases
    aliases = build_path_aliases("/nonexistent/path/file.py")
    assert aliases.absolute == "/nonexistent/path/file.py"
    assert aliases.realpath == "/nonexistent/path/file.py"
    assert aliases.basename == "file.py"

def test_matches_absolute():
    from audit.lib_path_normalizer import build_path_aliases, matches_path
    aliases = build_path_aliases("/tmp/test.py")
    matched, conf = matches_path("/tmp/test.py", aliases)
    assert matched is True
    assert conf == "high"

def test_matches_repo_relative():
    from audit.lib_path_normalizer import build_path_aliases, matches_path
    f = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    aliases = build_path_aliases(f)
    if aliases.repo_relative:
        matched, conf = matches_path(aliases.repo_relative, aliases)
        assert matched is True
        assert conf == "medium"

def test_basename_only_with_low_threshold():
    from audit.lib_path_normalizer import build_path_aliases, matches_path
    aliases = build_path_aliases("/some/path/file.py")
    matched, conf = matches_path("file.py", aliases, confidence_threshold="low")
    assert matched is True
    assert conf == "low"

def test_basename_rejected_at_medium_threshold():
    from audit.lib_path_normalizer import build_path_aliases, matches_path
    aliases = build_path_aliases("/some/path/file.py")
    matched, _ = matches_path("file.py", aliases, confidence_threshold="medium")
    assert matched is False

def test_no_match():
    from audit.lib_path_normalizer import build_path_aliases, matches_path
    aliases = build_path_aliases("/some/path/file.py")
    matched, _ = matches_path("/other/path/other.py", aliases)
    assert matched is False
