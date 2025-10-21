"""
File: lib_outputColors.py
Library for enabling colorized terminal output.

Provides blank/no-op implementation if dependency packages are not installed

@Dependencies termcolor, colorama
"""

import sys
import argparse

# Attempt to import termcolor
try:
    from termcolor import colored
except ImportError:

    def colored(text, color=None, on_color=None, attrs=None):
        """Fallback method implementation if termcolor isn't installed"""
        return text


# Attempt to import colorama
try:
    from colorama import Fore, Back, Style, init

    init(autoreset=True)
except ImportError:

    class Fore:
        """Fallback class implementation if colorama isn't installed"""

        RED = ""
        GREEN = ""
        YELLOW = ""
        RESET = ""

    class Back:
        """Fallback class implementation if colorama isn't installed"""

        YELLOW = ""
        BLUE = ""

    class Style:
        """Fallback class implementation if colorama isn't installed"""

        BRIGHT = ""
        DIM = ""
        RESET_ALL = ""


# Modified print_colored function
def colorize_string(text, fore_color=None, back_color=None, style=None):
    """Return a colorized string instead of printing it."""
    if fore_color:
        text = getattr(Fore, fore_color.upper(), "") + text
    if back_color:
        text = getattr(Back, back_color.upper(), "") + text
    if style:
        text = getattr(Style, style.upper(), "") + text

    return colored(text)


def print_colored(text, fore_color=None, back_color=None, style=None):
    """Print output with color if either termcolor or colorama are installed"""
    text = colorize_string(
        text, fore_color=fore_color, back_color=back_color, style=style
    )
    print(text)


def parse_args():
    """Parse command line args, even as an imported library"""
    parser = argparse.ArgumentParser(
        description="lib_outputColors Help/Usage Information"
    )
    parser.add_argument(
        "--help-color",
        action="store_true",
        help="Display help information for colors and styles",
    )

    args, _ = parser.parse_known_args()
    return args


def print_help_color():
    """Print colors usage"""
    print("Available Foreground Colors (Fore):")
    print("  RED, GREEN, YELLOW")
    print("\nAvailable Background Colors (Back):")
    print("  YELLOW, BLUE")
    print("\nAvailable Styles (Style):")
    print("  BRIGHT, DIM")
    print("\nUsage Examples:")
    print("  print_colored('Hello, World!', fore_color='red', style='bright')")
    print(
        "  print_colored('Warning!', fore_color='yellow', back_color='blue', style='dim')"
    )


def main():
    """Rare to use this function from the library"""
    args = parse_args()
    if args.help_color:
        print_help_color()
        sys.exit(0)

    # Add any other logic here if needed


if __name__ == "__main__":
    main()
