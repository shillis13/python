#!/usr/bin/env python3
"""Setup configuration for yaml_utils package."""

from setuptools import setup, find_packages

setup(
    name="yaml_utils",
    version="1.0.0",
    description="YAML processing and manipulation utilities",
    author="PianoMan",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pyyaml',
    ],
    # Console scripts - auto-generated
    entry_points={
        'console_scripts': [
            'yaml_detect_message_gaps=yaml_utils.yaml_detect_message_gaps:main',
            'yaml_read_key=yaml_utils.yaml_read_key:main',
            'yaml_add_item=yaml_utils.yaml_add_item:main',
            'yaml_stats=yaml_utils.yaml_stats:main',
            'yaml_prune=yaml_utils.yaml_prune:main',
            'yaml_validate=yaml_utils.yaml_validate:main',
            'yaml_tree_printer=yaml_utils.yaml_tree_printer:main',
            'yaml_chat_manager=yaml_utils.yaml_chat_manager:main',
            'yaml_shell=yaml_utils.yaml_shell:main',
            'yaml_chat_indexer=yaml_utils.yaml_chat_indexer:main',
            'yaml_summarize_chat_history=yaml_utils.yaml_summarize_chat_history:main',
            'yaml_convert_chat_history_v1.1=yaml_utils.yaml_convert_chat_history_v1.1:main',
            'yaml_update_key=yaml_utils.yaml_update_key:main',
            'extract_yaml_from_md=yaml_utils.extract_yaml_from_md:main',
            'yaml_merge=yaml_utils.yaml_merge:main',
            'yaml_delete_item=yaml_utils.yaml_delete_item:main',
        ],
    },

)