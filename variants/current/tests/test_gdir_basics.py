import shlex


def decode(res):
    return res.stdout.decode().strip()


def test_add_list_rm_clear(run_gdir, tmp_path):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()

    run_gdir("add", "alpha", str(d1))
    run_gdir("add", "beta", str(d2))

    out = decode(run_gdir("list"))
    lines = out.splitlines()
    assert lines[0].split("\t")[:2] == ["1", "alpha"]
    assert lines[1].split("\t")[:2] == ["2", "beta"]

    run_gdir("rm", "1")
    out = decode(run_gdir("list"))
    assert out.split("\t")[:2] == ["1", "beta"]

    run_gdir("clear", "--yes")
    out = decode(run_gdir("list"))
    assert out == ""


def test_go_back_fwd(run_gdir, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    run_gdir("add", "a", str(a))
    run_gdir("add", "b", str(b))

    go_res = decode(run_gdir("go", "a"))
    assert go_res == str(a.resolve())

    go_b = decode(run_gdir("go", "2"))
    assert go_b == str(b.resolve())

    back_res = decode(run_gdir("back"))
    assert back_res == str(a.resolve())

    fwd_res = decode(run_gdir("fwd"))
    assert fwd_res == str(b.resolve())

    err = run_gdir("go", "missing", check=False)
    assert err.returncode == 2


def test_history_persistence(run_gdir, tmp_path):
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    run_gdir("add", "one", str(one))
    run_gdir("add", "two", str(two))

    run_gdir("go", "one")
    run_gdir("go", "two")

    back_res = decode(run_gdir("back"))
    assert back_res == str(one.resolve())

    fwd_res = decode(run_gdir("fwd"))
    assert fwd_res == str(two.resolve())


def test_env_exports(run_gdir, tmp_path):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()

    run_gdir("add", "d1", str(d1))
    run_gdir("add", "d2", str(d2))
    run_gdir("go", "d1")
    run_gdir("go", "d2")

    env_out = run_gdir("env").stdout.decode().strip().splitlines()
    expected_prev = f"export GDIR_PREV={shlex.quote(str(d1.resolve()))}"
    assert env_out[0] == expected_prev
    assert env_out[1] == "export GDIR_NEXT=''"


def test_help(run_gdir):
    result = run_gdir("--help")
    text = result.stdout.decode()
    assert "usage:" in text.lower()
    assert "Examples:" in text
