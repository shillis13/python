#!/usr/bin/env python3
"""Setup configuration for terminal_utils package."""

from setuptools import setup, find_packages

setup(
    name="terminal_utils",
    version="1.0.0",
    description="Terminal and console utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'cleanhist=terminal_utils.cleanhist:main',
        ],
    },

)