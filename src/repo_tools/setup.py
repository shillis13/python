#!/usr/bin/env python3
"""Setup configuration for repo_tools package."""

from setuptools import setup, find_packages

setup(
    name="repo_tools",
    version="1.0.0",
    description="Repository management and Git utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'pygit=repo_tools.pygit:main',
        ],
    },

)