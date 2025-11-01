"""
Chat Processing Package

This package provides tools for converting chat histories between various formats.
"""

__version__ = "2.0.0"

# Make submodules available at package level
from . import lib_converters
from . import lib_parsers
from . import lib_formatters
