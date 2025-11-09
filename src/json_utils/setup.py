#!/usr/bin/env python3
"""Setup configuration for json_utils package."""

from setuptools import setup, find_packages

setup(
    name="json_utils",
    version="1.0.0",
    description="JSON processing and manipulation utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'md_to_json_converter=json_utils.archive.md_to_json_converter:main',
            'json_to_chat_html=json_utils.archive.json_to_chat_html:main',
            'json_chat_filter=json_utils.json_chat_filter:main',
            'json_chunker=json_utils.json_chunker:main',
        ],
    },

)