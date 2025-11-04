#!/usr/bin/env python3
"""Setup configuration for ai_utils package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README if it exists
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="ai_utils",
    version="1.0.0",
    description="AI utilities for chat processing and conversion",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PianoMan",
    python_requires=">=3.8",

    # Find all packages (chat_processing, etc.)
    packages=find_packages(),

    # Include package data (schemas, etc.)
    include_package_data=True,
    package_data={
        'chat_processing': ['schemas/*.json', 'schemas/*.yaml'],
    },

    # Dependencies
    install_requires=[
        # Add any required packages here
        # 'pyyaml',  # if needed
    ],

    # Console scripts - makes commands available system-wide
    entry_points={
        'console_scripts': [
            'chat-converter=chat_processing.chat_converter:main',
            'doc-converter=chat_processing.doc_converter:main',
            'chats-splitter=chat_processing.chats_splitter:main',
        ],
    },

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
)
