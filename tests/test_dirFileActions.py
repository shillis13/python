
def test_read_filenames_from_file():
    # Setup
    create_test_file("filenames.txt", ["file1.txt", "file2.txt", "file3.txt"])
    create_test_files(["file1.txt", "file2.txt"])  # Assuming file3.txt does not exist

    # Execution
    execute_script("--from-file filenames.txt --delete")

    # Assertion
    assert not os.path.exists("file1.txt"), "file1.txt should be deleted"
    assert not os.path.exists("file2.txt"), "file2.txt should be deleted"
    assert os.path.exists("file3.txt"), "file3.txt should not exist and thus not deleted"

    # Cleanup
    cleanup_test_files(["file1.txt", "file2.txt", "filenames.txt"])


def test_read_filenames_from_stdin():
    # Setup
    create_test_files(["file1.txt", "file2.txt"])

    # Execution
    simulate_stdin_input("file1.txt\nfile2.txt", "--delete")

    # Assertion
    assert not os.path.exists("file1.txt"), "file1.txt should be deleted"
    assert not os.path.exists("file2.txt"), "file2.txt should be deleted"

    # Cleanup
    cleanup_test_files(["file1.txt", "file2.txt"])


def test_filenames_from_command_line():
    # Setup
    create_test_files(["file1.txt", "file2.txt"])

    # Execution
    execute_script("--delete file1.txt file2.txt")

    # Assertion
    assert not os.path.exists("file1.txt"), "file1.txt should be deleted"
    assert not os.path.exists("file2.txt"), "file2.txt should be deleted"

    # Cleanup
    cleanup_test_files(["file1.txt", "file2.txt"])



