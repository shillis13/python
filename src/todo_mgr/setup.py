#!/usr/bin/env python3
"""Setup configuration for todo_mgr package."""

from setuptools import setup
from pathlib import Path

# Read README if it exists
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="todo_mgr",
    version="1.0.0",
    description="todo_mgr package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",

    # Individual modules (flat structure, no __init__.py)
    py_modules=['todo_mgr'],

    # Dependencies
    install_requires=[
        # Add any required packages here
    ],

    # Classifiers for PyPI (if you ever publish)
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],

    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'todo_mgr=todo_mgr:main',
        ],
    },

)