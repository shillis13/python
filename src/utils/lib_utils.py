""" 
File: lib_utils.py
"""
import re
#import logging
import argparse


def glob_to_regex(pattern):
    """
    Convert a simple glob pattern to a regex pattern, ensuring it doesn't
    unnecessarily escape $ at the end or add ^ or $ if they already exist.
    """
    # Check if pattern ends with an unescaped $, indicating intention to use it as regex end-of-line anchor
    ends_with_dollar = pattern.endswith('$')

    # Escape special characters in regex, except for * and ? and an ending $
    if ends_with_dollar:
        pattern = pattern[:-1]  # Remove the trailing $ to avoid escaping it
    pattern = re.escape(pattern)
    if ends_with_dollar:
        pattern += '$'  # Re-append the unescaped $

    # Replace glob * and ? with their regex equivalents
    pattern = pattern.replace(r'\*', '.*').replace(r'\?', '.')

    # Ensure the pattern matches the entire string, checking for ^ and $
    if not pattern.startswith('^'):
        pattern = '^' + pattern
    # No need to add $ at the end if it's already there
    if not pattern.endswith('$'):
        pattern = pattern + '$'

    return pattern


'''
# Example
glob_pattern = '*.txt'
regex_pattern = glob_to_regex(glob_pattern)
print(f"Glob pattern: {glob_pattern}\nRegex pattern: {regex_pattern}")
'''



def handle_pause_at_startup():
    parser = argparse.ArgumentParser(description="A script with optional pause at startup.")
    parser.add_argument('--pause-at-startup', action='store_true', help='Pause the script at startup until Enter is pressed.')
    args, _ = parser.parse_known_args()
    # args = parser.parse_args()

    if args.pause_at_startup:
        input("Press Enter to continue...")

    return args
