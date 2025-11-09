#!/usr/bin/env python3
"""Setup configuration for email_tools package."""

from setuptools import setup, find_packages

setup(
    name="email_tools",
    version="1.0.0",
    description="Email handling and processing tools",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'cli_gmail=email_tools.gmail_client.cli_gmail:main',
        ],
    },

)