#!/usr/bin/env python3
"""
pygrep.py: Minimal grep-like tool supporting BRE and ERE modes.

Usage:
    python pygrep.py --pattern 'PATTERN' --mode bre --file sample.txt
    python pygrep.py --pattern 'PATTERN' --mode ere --file sample.txt
"""
import argparse
import re
import sys

def bre_to_python(pattern):
    # Parentheses: \(...\) -> (...)
    pattern = re.sub(r'\\\((.*?)\\\)', r'(\1)', pattern)
    # Curly braces: \{m,n\} -> {m,n}
    pattern = re.sub(r'\\\{(\d+,\d*)\\\}', r'{\1}', pattern)
    # Plus: \+ -> +
    pattern = pattern.replace(r'\+', '+')
    # Question: \? -> ?
    pattern = pattern.replace(r'\?', '?')
    return pattern

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pattern', required=True, help='Regex pattern')
    parser.add_argument('--mode', choices=['bre', 'ere'], required=True)
    parser.add_argument('--file', required=True)
    args = parser.parse_args()

    if args.mode == 'bre':
        pattern = bre_to_python(args.pattern)
    else:
        pattern = args.pattern

    try:
        prog = re.compile(pattern)
    except re.error as e:
        print(f"Regex compile error: {e}")
        sys.exit(1)

    with open(args.file, encoding='utf-8') as f:
        for line in f:
            if prog.search(line):
                print(line.rstrip('\n'))

if __name__ == '__main__':
    main()

