import sys
import argparse
import pandas as pd
from lib_treeFcns import Fcn_FindCircularDependencies


def main():
    """Main"""
    parser = argparse.ArgumentParser(
        description="Find circular dependencies in a ParentChildTable."
    )
    parser.add_argument(
        "filename", type=str, help="The CSV file containing the ParentChildTable."
    )
    parser.add_argument(
        "--encoding", type=str, default="utf-8", help="File encoding (default: utf-8)."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print the first 10 records of circular dependency nodes.",
    )
    parser.add_argument(
        "--verbose-all",
        action="store_true",
        help="Print all records of circular dependency nodes.",
    )
    args, _ = parser.parse_known_args()
    # args = parser.parse_args()

    # Read the ParentChildTable from CSV file with specified encoding
    try:
        df = pd.read_csv(args.filename, encoding=args.encoding)
    except UnicodeDecodeError as e:
        try:
            print(
                f"Error reading the file with encoding {args.encoding}: {e}\nAttempting alternate encoding"
            )
            df = pd.read_csv(args.filename, encoding="ISO-8859-1")
        except UnicodeDecodeError as ex:
            print(f"Error reading the file with encoding 'ISO-8859-1': {ex}")
            sys.exit(1)

    # Find circular dependencies
    circular_df = Fcn_FindCircularDependencies(df)

    # Remove duplicate ParentKey-ChildKey pairs
    circular_df = circular_df.drop_duplicates(subset=["ParentKey", "ChildKey"])

    circular_nodes = pd.concat(
        [circular_df["ParentKey"], circular_df["ChildKey"]]
    ).unique()

    # Print the number of circular dependencies found
    print(f"Number of circular dependencies found: {len(circular_nodes)}")

    # If verbose flag is set, print the first 10 circular dependencies
    if args.verbose:
        print("First 10 circular dependency records:")
        print(circular_df.head(10))

    # If verbose-all flag is set, print all circular dependencies
    if args.verbose_all:
        print("All circular dependency records:")
        print(circular_df)


if __name__ == "__main__":
    main()
