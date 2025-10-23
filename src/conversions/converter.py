#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal File Converter - Main Entry Point

This is the primary converter script that automatically detects file types
and routes to the appropriate specialized converter (chat or document).

This script is an alias/wrapper for file_converter.py for convenience.
"""

import sys
import os

# Add the current directory to the path so we can import file_converter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main file converter
from file_converter import main

if __name__ == "__main__":
    main()