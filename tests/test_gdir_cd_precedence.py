from __future__ import annotations

import subprocess

from gdir.godir import EXIT_INVALID, _BASH_WRAPPER, main
from gdir.store import MappingStore


def test_exact_bookmark_resolver_precedes_command_names(tmp_path, capsys):
    target = tmp_path / "saved-list"
    target.mkdir()
    config = tmp_path / "config"
    store = MappingStore.load(config)
    store.add("list", str(target))
    store.save()

    assert main(("--config", str(config), "resolve", "list")) == 0
    assert capsys.readouterr().out.strip() == str(target.resolve())
    assert main(("--config", str(config), "resolve", "missing")) == EXIT_INVALID


def test_generated_cd_wrapper_encodes_the_five_stage_precedence():
    direct = _BASH_WRAPPER.index('[[ $# -eq 1 && -d "$1" ]]')
    saved = _BASH_WRAPPER.index('"$_GDIR_BIN" resolve "$1"')
    command = _BASH_WRAPPER.index("# 3. Only now interpret param0 as a gdir command.")
    fuzzy = _BASH_WRAPPER.index("# 4. Fall back to zoxide fuzzy resolution.")
    error = _BASH_WRAPPER.index("# 5. Nothing resolved.")
    assert direct < saved < command < fuzzy < error

    checked = subprocess.run(
        ("bash", "-n"),
        input=_BASH_WRAPPER,
        text=True,
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
