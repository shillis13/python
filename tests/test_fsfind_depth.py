import os
import sys
import subprocess
from pathlib import Path


def run_fsfind(*args, cwd=None):
    """Run fsFind as a module; return (code, stdout, stderr)."""
    cmd = [sys.executable, "-m", "file_utils.fsFind", *map(str, args)]
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def build_tree(root: Path):
    """Build a small directory tree used by depth tests."""
    a = root / "a"
    b = a / "b"
    c = b / "c"
    a.mkdir()
    b.mkdir()
    c.mkdir()
    (a / "file1.txt").write_text("x", encoding="utf-8")
    dlink = root / "dlink"
    try:
        if hasattr(os, "symlink"):
            if dlink.exists() or dlink.is_symlink():
                dlink.unlink()
            os.symlink(b, dlink, target_is_directory=True)
    except (OSError, NotImplementedError):
        dlink = None
    return a, b, c, dlink


def lines_list(stdout: str):
    return [ln for ln in stdout.splitlines() if ln.strip()]


def contains_any(paths, needle: str):
    return any(needle in p for p in paths)


def test_no_double_emit_with_min_depth(tmp_path):
    start, b, _, _ = build_tree(tmp_path)
    code, out, err = run_fsfind("--include-dirs", "--min-depth", "1", str(start))
    assert code == 0, f"non-zero exit: {err}"
    lines = lines_list(out)
    # Ensure no duplicates
    assert len(lines) == len(set(lines)), f"duplicate emits detected:\n{out}"
    # Depth 0 corresponds to children of the start directories
    assert contains_any(lines, str(b.resolve())), out
    assert contains_any(lines, str((start / "file1.txt").resolve())), out


def test_max_depth_limits_descent(tmp_path):
    start, b, c, _ = build_tree(tmp_path)
    code, out, err = run_fsfind("--include-dirs", "--max-depth", "1", str(start))
    assert code == 0, f"non-zero exit: {err}"
    lines = lines_list(out)
    # Depth-1 entries are present
    assert contains_any(lines, str(b.resolve())), out
    # But grandchildren (depth 2) are not
    assert not contains_any(lines, str(c.resolve())), out


def test_invalid_depth_args(tmp_path):
    start, *_ = build_tree(tmp_path)
    code, out, err = run_fsfind("--min-depth", "3", "--max-depth", "1", str(start))
    assert code != 0
    msg = (out + "\n" + err).lower()
    assert "min-depth" in msg and "max-depth" in msg


def test_symlink_depth_respected(tmp_path):
    _, _, c, dlink = build_tree(tmp_path)
    if dlink is None:
        import pytest

        pytest.skip("symlinks not supported on this platform")
    code, out, err = run_fsfind(
        "--include-dirs", "--follow-symlinks", "--max-depth", "1", str(tmp_path)
    )
    assert code == 0, f"non-zero exit: {err}"
    lines = lines_list(out)
    # Depth cap should still prevent reaching 'c' via the symlink path
    assert not contains_any(lines, str(c.resolve())), out
