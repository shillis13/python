#!/usr/bin/env python3
"""Setup configuration for metadata_utils package."""

from setuptools import setup, find_packages

setup(
    name="metadata_utils",
    version="1.0.0",
    description="Metadata extraction and management utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'dir_struct_discovery=metadata_utils.dir_struct_discovery:main',
        ],
    },

)