#!/usr/bin/env python3
"""Setup configuration for dev_utils package."""

from setuptools import setup, find_packages

setup(
    name="dev_utils",
    version="1.0.0",
    description="Development utilities and helper tools",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'compile_check=dev_utils.compile_check:main',
        ],
    },

)