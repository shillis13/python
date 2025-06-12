#!/usr/bin/env python3

import csv
import os
import re

# Default directory and file path
DEFAULT_CSV_DIR = os.getcwd()  # Current working directory as default
DEFAULT_CSV_FILENAME = "extensions.csv"
DEFAULT_CSV_PATH = os.path.join(DEFAULT_CSV_DIR, DEFAULT_CSV_FILENAME)

# Global variable to store the merged extension info dictionary
_extension_info = None

def ExtensionInfo(csv_filename=DEFAULT_CSV_PATH):
    global _extension_info
    if _extension_info is None:
        _extension_info = load_and_merge_data(csv_filename)
    return _extension_info

def load_and_merge_data(csv_filename):
    extensions_dict = {}
    category_dict = {}

    # Temporary dict to store extensions by category for building regex
    extensions_by_category = {}

    # Reading the CSV file
    with open(csv_filename, mode='r') as file:
        reader = csv.DictReader(file)

        for row in reader:
            ext = row['extension']
            category = row['category']
            name = row['name']
            description = row['description']

            # Add extension-level info
            if ext not in extensions_dict:
                extensions_dict[ext] = {
                    'name': name,
                    'category': category,
                    'description': description
                }

            # Collect extensions by category for regex generation
            if category not in category_dict:
                category_dict[category] = {
                    'extensions': [],
                    'regex': None  # To be generated later
                }
            category_dict[category]['extensions'].append(ext)

            # Collect for regex creation
            if category not in extensions_by_category:
                extensions_by_category[category] = []
            extensions_by_category[category].append(ext)

    # Build the regex for each category and merge it into the category_dict
    for category, extensions in extensions_by_category.items():
        regex_pattern = r"\.(" + "|".join([re.escape(ext.lstrip(".")) for ext in extensions]) + ")$"
        category_dict[category]['regex'] = regex_pattern

    # Merge extension and category dictionaries into one
    merged_dict = {**extensions_dict, **category_dict}
    return merged_dict

# Command-line argument parsing to override CSV filepath
def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Load and parse extension info from a CSV file.")
    parser.add_argument('--csv', type=str, default=DEFAULT_CSV_PATH, help="Path to the CSV file")
    return parser.parse_args()

# Function to print extensions_info with one-line print statements
def print_extensions_info(extensions_info):
    print("Extension dictionary loaded:")
    for ext, info in extensions_info.items():
        print(f"Extension: {ext}, Category: {info.get('category', 'N/A')}, Name: {info.get('name', 'N/A')}, Description: {info.get('description', 'N/A')}")

# Function to print category_info with one-line print statements
def print_category_info(extensions_info):
    print("Category dictionary loaded:")
    for category, info in extensions_info.items():
        if 'extensions' in info:
            print(f"Category: {category}, Extensions: {', '.join(info['extensions'])}, Regex: {info['regex']}")

# Main function to handle loading and parsing of the CSV file
def main():
    # Parse the command-line arguments
    args = parse_args()

    # Load extension data from the specified or default CSV file
    csv_file_path = args.csv
    print(f"Loading data from: {csv_file_path}")

    # Call the ExtensionInfo function to parse the CSV
    extensions_info = ExtensionInfo(csv_file_path)

    # Print the dictionaries with one-line prints
    print_extensions_info(extensions_info)
    print("")
    print_category_info(extensions_info)


# Load extensions from extensions.csv
def load_extensions_from_csv(csv_filename):
    extensions_set = set()  # Use a set to store unique extensions
    with open(csv_filename, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            ext = row['extension'].strip().lower()
            extensions_set.add(ext)
    return extensions_set

# Load extensions from the magic file
def load_extensions_from_magic(magic_filename):
    extensions_set = set()
    with open(magic_filename, mode="r") as file:
        for line in file:
            # Look for lines that mention extensions (this can vary by magic file format)
            match = re.search(r'!(?:mime|ext)\s+([a-zA-Z0-9/.-]+)', line)
            if match:
                ext = match.group(1).split('/')[-1].strip().lower()
                extensions_set.add(f".{ext}")
    return extensions_set

# Compare extensions
def compare_extensions(csv_extensions, magic_extensions):
    missing_in_csv = magic_extensions - csv_extensions
    missing_in_magic = csv_extensions - magic_extensions
    return missing_in_csv, missing_in_magic



# Entry point
if __name__ == "__main__":
    main()

