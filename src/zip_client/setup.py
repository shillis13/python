#!/usr/bin/env python3
"""Setup configuration for zip_client package."""

from setuptools import setup, find_packages

setup(
    name="zip_client",
    version="1.0.0",
    description="ZIP archive utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,


    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
        ],
    },

)