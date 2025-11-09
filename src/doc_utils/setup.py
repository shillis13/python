#!/usr/bin/env python3
"""Setup configuration for doc_utils package."""

from setuptools import setup, find_packages

setup(
    name="doc_utils",
    version="1.0.0",
    description="Document processing and manipulation utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'manpage=doc_utils.manpage:main',
        ],
    },

)