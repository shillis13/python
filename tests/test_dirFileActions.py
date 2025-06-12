import os
import shlex
import shutil

TEST_DIR = "test_dirFileActions"


def create_test_file(name, lines):
    os.makedirs(TEST_DIR, exist_ok=True)
    with open(os.path.join(TEST_DIR, name), "w") as f:
        f.write("\n".join(lines))


def create_test_files(files):
    os.makedirs(TEST_DIR, exist_ok=True)
    for f in files:
        open(os.path.join(TEST_DIR, f), "w").close()


def cleanup_test_files(files=None):
    if files is None:
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
    else:
        for f in files:
            path = os.path.join(TEST_DIR, f)
            if os.path.exists(path):
                os.remove(path)


def execute_script(args):
    tokens = shlex.split(args)
    delete = "--delete" in tokens
    filenames = []
    if "--from-file" in tokens:
        idx = tokens.index("--from-file")
        fname = tokens[idx + 1]
        with open(os.path.join(TEST_DIR, fname)) as f:
            filenames = [line.strip() for line in f if line.strip()]
    else:
        filenames = [t for t in tokens if not t.startswith("--")]
        if delete and filenames and filenames[0] == "--delete":
            filenames = filenames[1:]
    if delete:
        for f in filenames:
            path = os.path.join(TEST_DIR, f)
            if os.path.exists(path):
                os.remove(path)


def simulate_stdin_input(stdin_data, args):
    tokens = shlex.split(args)
    if "--delete" in tokens:
        for line in stdin_data.splitlines():
            path = os.path.join(TEST_DIR, line)
            if os.path.exists(path):
                os.remove(path)


def test_read_filenames_from_file():
    create_test_file("filenames.txt", ["file1.txt", "file2.txt", "file3.txt"])
    create_test_files(["file1.txt", "file2.txt"])
    execute_script("--from-file filenames.txt --delete")
    assert not os.path.exists(os.path.join(TEST_DIR, "file1.txt"))
    assert not os.path.exists(os.path.join(TEST_DIR, "file2.txt"))
    assert not os.path.exists(os.path.join(TEST_DIR, "file3.txt"))
    cleanup_test_files()


def test_read_filenames_from_stdin():
    create_test_files(["file1.txt", "file2.txt"])
    simulate_stdin_input("file1.txt\nfile2.txt", "--delete")
    assert not os.path.exists(os.path.join(TEST_DIR, "file1.txt"))
    assert not os.path.exists(os.path.join(TEST_DIR, "file2.txt"))
    cleanup_test_files()


def test_filenames_from_command_line():
    create_test_files(["file1.txt", "file2.txt"])
    execute_script("--delete file1.txt file2.txt")
    assert not os.path.exists(os.path.join(TEST_DIR, "file1.txt"))
    assert not os.path.exists(os.path.join(TEST_DIR, "file2.txt"))
    cleanup_test_files()
