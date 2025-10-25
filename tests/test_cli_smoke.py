from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from gdir import cli


def test_cli_add_go_env(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = tmp_path / "cfg"
    target = tmp_path / "target"
    target.mkdir()

    code = cli.main(["--config", str(config_dir), "add", "code", str(target)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Saved code" in out

    code = cli.main(["--config", str(config_dir), "list"])
    out = capsys.readouterr().out
    assert "code" in out

    code = cli.main(["--config", str(config_dir), "go", "code"])
    output = capsys.readouterr()
    assert code == 0
    assert output.out.strip() == str(target.resolve())

    code = cli.main(["--config", str(config_dir), "back"])
    output = capsys.readouterr()
    assert code == cli.EXIT_INVALID
    assert "No previous" in output.err

    code = cli.main(["--config", str(config_dir), "env", "--format", "sh"])
    output = capsys.readouterr()
    assert code == 0
    assert "GODIR_PREV" in output.out

    code = cli.main(["--config", str(config_dir), "save"])
    assert code == 0
    capsys.readouterr()

    code = cli.main(["--config", str(config_dir), "doctor"])
    output = capsys.readouterr()
    assert code == 0
    assert "Configuration directory" in output.out
