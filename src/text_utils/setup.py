#!/usr/bin/env python3
"""Setup configuration for text_utils package."""

from setuptools import setup
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="text_utils",
    version="1.0.0",
    description="Text cleaning, formatting, and markdown table utilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PianoMan",
    python_requires=">=3.8",
    packages=["text_utils"],
    package_dir={"text_utils": "."},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "clean_text=text_utils.clean_text:main",
            "text_formatter=text_utils.text_formatter:main",
            "md_table_reformat=text_utils.md_table_reformat:main",
            "field_reorder=text_utils.field_reorder:main",
        ],
    },
)
