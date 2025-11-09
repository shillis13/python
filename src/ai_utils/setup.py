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
            'codex_manager=ai_utils.codex_manager:main',
            'liaison=ai_utils.FILE.liaison:main',
            'chat_chunker=ai_utils.chat_processing.chat_chunker:main',
            'doc_converter=ai_utils.chat_processing.doc_converter:main',
            'chat_converter=ai_utils.chat_processing.chat_converter:main',
            'md_structure_parser=ai_utils.chat_processing.md_structure_parser:main',
            'chats_splitter=ai_utils.chat_processing.chats_splitter:main',
            'batch_md_to_yaml=ai_utils.chat_processing.batch_md_to_yaml:main',
            'python_chat_utilities=ai_utils.chat_continuity_protocol.python_chat_utilities:main',
            'simple_schema_validator=ai_utils.validation.simple_schema_validator:main',
            'distribute_ai_files=ai_utils.distribute_ai_files:main',
        ],
    },

)