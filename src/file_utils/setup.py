#!/usr/bin/env python3
"""Setup configuration for file_utils package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README if it exists
readme_file = Path(__file__).parent / "file_utils_README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="file_utils",
    version="1.0.0",
    description="File system utilities for finding, filtering, and formatting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts
    entry_points={
        'console_scripts': [
            'fsFormat=file_utils.fsFormat:main',
            'fsFind=file_utils.fsFind:main',
            'gen_random_files_dirs=file_utils.gen_random_files_dirs:main',
            'renameFiles=file_utils.renameFiles:main',
            'fsFilters=file_utils.fsFilters:main',
            'pygrep=file_utils.pygrep:main',
            'treePrint=file_utils.treePrint:main',
            'fsActions=file_utils.fsActions:main',
        ],
    },

)