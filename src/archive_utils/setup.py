#!/usr/bin/env python3
"""Setup configuration for archive_utils package."""

from setuptools import setup, find_packages

setup(
    name="archive_utils",
    version="1.0.0",
    description="Utilities for archive management and processing",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'cli_archive=archive_utils.cli_archive:main',
            'fileBackup=archive_utils.fileBackup:main',
        ],
    },

)