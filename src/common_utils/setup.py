#!/usr/bin/env python3
"""Setup configuration for common_utils package."""

from setuptools import setup, find_packages

setup(
    name="common_utils",
    version="2.0.0",
    description="Shared Python utilities — colors, file I/O, logging, argparse, dry-run",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'compile_check=common_utils.compile_check:main',
        ],
    },
)