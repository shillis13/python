from gdir import cli


def run_cli(tmp_path, *args):
    argv = ["--config", str(tmp_path)] + list(args)
    return cli.main(argv)


def test_add_and_go(tmp_path, capsys):
    target = tmp_path / "destination"
    target.mkdir()
    code = run_cli(tmp_path, "add", "home", str(target))
    assert code == 0
    capsys.readouterr()
    code = run_cli(tmp_path, "go", "home")
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(target.resolve())


def test_go_invalid_key(tmp_path, capsys):
    code = run_cli(tmp_path, "go", "missing")
    assert code == cli.EXIT_INVALID
    captured = capsys.readouterr()
    assert "Unknown mapping" in captured.err


def test_env_output(tmp_path, capsys):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    run_cli(tmp_path, "add", "first", str(first))
    run_cli(tmp_path, "add", "second", str(second))
    capsys.readouterr()
    run_cli(tmp_path, "go", "first")
    capsys.readouterr()
    run_cli(tmp_path, "go", "second")

    code = run_cli(tmp_path, "env", "--format", "sh")
    assert code == 0
    output = capsys.readouterr().out
    assert "GODIR_PREV" in output
    assert "GODIR_NEXT" not in output  # no forward entry yet

    code = run_cli(tmp_path, "back")
    assert code == 0
    capsys.readouterr()
    code = run_cli(tmp_path, "env", "--format", "sh")
    assert code == 0
    output = capsys.readouterr().out
    assert "GODIR_NEXT" in output


def test_hist_command(tmp_path, capsys):
    for idx in range(3):
        folder = tmp_path / f"dir{idx}"
        folder.mkdir()
        run_cli(tmp_path, "add", f"k{idx}", str(folder))
        run_cli(tmp_path, "go", f"k{idx}")
        capsys.readouterr()
    code = run_cli(tmp_path, "hist", "--before", "1", "--after", "1")
    assert code == 0
    output = capsys.readouterr().out
    assert "➤" in output


def test_import_missing_file(tmp_path, capsys):
    code = run_cli(tmp_path, "import", "cdargs")
    assert code == cli.EXIT_INVALID
    assert "cdargs file not found" in capsys.readouterr().err
