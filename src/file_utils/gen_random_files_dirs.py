#!/usr/bin/env python3

import os
import random
import string
import nltk
import itertools
import argparse

nltk.download("words")
from nltk.corpus import words

word_list = words.words()

# Define a cycle of separators
separators = itertools.cycle(["", " ", "_", "-", "."])


def create_random_word(separator, include_special_chars=False):
    """
    Creates a random word using a random selection of words from the nltk words list,
    joining them with the specified separator.

    Args:
        separator (str): The separator to use between words.
        include_special_chars (bool): If True, add random special characters to the word.

    Returns:
        str: A string of randomly combined words using the specified separator.
    """
    word = separator.join(random.choices(word_list, k=random.randint(1, 3))).lower()
    if include_special_chars:
        special_chars = "".join(
            random.choices(string.punctuation, k=random.randint(1, 3))
        )
        word += special_chars
    return word


def create_dir_structure(
    topDir,
    maxDepth,
    filesPerDir,
    subDirsPerDir,
    extensions,
    include_special_chars=False,
):
    """
    Creates a directory structure for testing.

    Args:
        topDir (str): The top directory under which the structure will be created.
        maxDepth (int): The maximum depth of directories to create.
        filesPerDir (int): The number of files to create in each directory.
        subDirsPerDir (int): The number of subdirectories to create in each directory.
        extensions (list): A list of file extensions to use for the created files.
        include_special_chars (bool): If True, include special characters in the filenames.
    """
    if not os.path.exists(topDir):
        os.makedirs(topDir)

    if maxDepth < 1:
        return

    extension_index = 0
    # For each file, select a separator and create a random name
    for i in range(filesPerDir):
        separator = next(separators)  # Get the next separator from the cycle
        extension = extensions[extension_index % len(extensions)]
        basename = create_random_word(
            separator, include_special_chars
        )  # Use the selected separator
        file_path = os.path.join(topDir, f"{basename}_{i}{extension}")
        with open(file_path, "w") as f:
            f.write("Test content\n")
        extension_index += 1

    # Base case: if maxDepth is 1, do not create any new subdirectories
    if maxDepth == 1:
        return

    # For each subdirectory, also select a separator and create a random name
    for i in range(subDirsPerDir):
        separator = next(separators)  # Get the next separator for the subdir name
        subdirName = create_random_word(
            separator, include_special_chars
        )  # Use the selected separator
        new_dir = os.path.join(topDir, f"{subdirName}_{i}")
        os.makedirs(new_dir, exist_ok=True)
        create_dir_structure(
            new_dir,
            maxDepth - 1,
            filesPerDir,
            subDirsPerDir,
            extensions,
            include_special_chars,
        )


def main():
    """
    Command-line interface for generating a test directory structure with files.

    Example usages:
    - Create a basic directory structure:
        python test_genFilesDirs.py --topDir test_data --maxDepth 3 --filesPerDir 5 --subDirsPerDir 2 --extensions .txt .md

    - Generate a more complex structure with different file extensions:
        python test_genFilesDirs.py --topDir complex_test_data --maxDepth 4 --filesPerDir 10 --subDirsPerDir 3 --extensions .txt .md .json

    Note: This script uses the NLTK words list to generate random file and directory names.
    """
    parser = argparse.ArgumentParser(
        description="Generate a test directory structure with random files and directories."
    )
    parser.add_argument(
        "--topDir",
        "-td",
        required=True,
        help="The top directory under which the structure will be created.",
    )
    parser.add_argument(
        "--maxDepth",
        "-md",
        type=int,
        required=True,
        help="The maximum depth of directories to create.",
    )
    parser.add_argument(
        "--filesPerDir",
        "-nf",
        type=int,
        required=True,
        help="The number of files to create in each directory.",
    )
    parser.add_argument(
        "--subDirsPerDir",
        "-nd",
        type=int,
        required=True,
        help="The number of subdirectories to create in each directory.",
    )
    parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        required=True,
        help="A list of file extensions to use for the created files. Provide each extension starting with a dot, separated by spaces.",
    )
    parser.add_argument(
        "--special-chars",
        "-sc",
        action="store_true",
        help="Include special characters in filenames.",
    )

    args, _ = parser.parse_known_args()
    # args = parser.parse_args()

    # Call the create_dir_structure function with the parsed arguments
    create_dir_structure(
        args.topDir,
        args.maxDepth,
        args.filesPerDir,
        args.subDirsPerDir,
        args.extensions,
        args.special_chars,
    )


if __name__ == "__main__":
    main()
