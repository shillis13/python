import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def home_tmp_path(tmp_path, monkeypatch):
    config_home = tmp_path / "home"
    config_home.mkdir()
    monkeypatch.setenv("HOME", str(config_home))
    return config_home


@pytest.fixture
def run_gdir(home_tmp_path):
    script = Path(__file__).resolve().parents[1] / "src" / "gdir.py"

    def _run(*args, input_text=None, check=True):
        result = subprocess.run(
            [sys.executable, str(script), *args],
            input=input_text.encode() if input_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=dict(os.environ),
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"gdir {' '.join(args)} failed with {result.returncode}: {result.stderr.decode()}"
            )
        return result

    return _run
