import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'


def remove_columns(df, columns_to_remove):
    current_columns = df.columns.tolist()
    valid_columns_to_remove = [col for col in columns_to_remove if col in current_columns]
    return df.drop(columns=valid_columns_to_remove)


def generate_unique_name(df, column_name, suffix):
    new_column_name = f"{column_name}_{suffix:02d}"
    while new_column_name in df.columns:
        suffix += 1
        new_column_name = f"{column_name}_{suffix:02d}"
    return new_column_name


def rename_columns(df, column_pairs):
    for src, dest in column_pairs:
        if src in df.columns:
            if dest in df.columns:
                dest = generate_unique_name(df, dest, 1)
            df = df.rename(columns={src: dest})
    return df


def add_columns(df, columns):
    for col_def in columns:
        col_name = col_def['ColumnName']
        value = col_def['Value']
        dtype = col_def.get('Type', 'object')
        if col_name not in df.columns:
            df.loc[:, col_name] = value
            if dtype == 'number':
                df.loc[:, col_name] = df.loc[:, col_name].astype(float)  # Default to float for numeric values
            else:
                df.loc[:, col_name] = df.loc[:, col_name].astype(dtype)
    return df


def fix_column_types(df, column_types):
    for col, dtype in column_types:
        if col in df.columns:
            df.loc[:, col] = pd.to_datetime(df[col]) if dtype == 'datetime64[ns]' else df[col].astype(dtype)
            if dtype == 'number':
                df.loc[:, col] = df.loc[:, col].fillna(0)
    return df


def remove_other_columns(df, columns_to_retain, exact_match=True):
    if exact_match:
        retained_columns = [col for col in df.columns if col in columns_to_retain]
    else:
        retained_columns = [col for col in df.columns if any(sub in col for sub in columns_to_retain)]
    return df[retained_columns]


def Fcn_CountUnique(df, columns_to_consider, count_non_unique=False):
    """
    Counts the number of unique or non-unique rows in a DataFrame based on specified columns.

    Parameters:
    df (pd.DataFrame): The DataFrame to analyze.
    columns_to_consider (list of str): The columns to consider for determining uniqueness.
    count_non_unique (bool): If True, return the count of non-unique rows. If False, return the count of unique rows.

    Returns:
    int: The count of unique or non-unique rows.
    """
    # Group by the specified columns and count the number of occurrences of each group
    counts = df.groupby(columns_to_consider).size()
    # print(f"Counts DF = \n{counts}")

    if count_non_unique:
        # Filter to keep only the groups with more than one occurrence
        non_unique_counts = counts[counts > 1]
        # Get the total number of non-unique rows
        num_non_unique = len(non_unique_counts)
        return num_non_unique
    else:
        # Filter to keep only the groups with exactly one occurrence
        unique_counts = counts[counts == 1]
        # Get the total number of unique rows
        num_unique = len(unique_counts)
        return num_unique


# *****************************************************************
# Test Functions
# *****************************************************************
def test_Fcn_CountUnique():
    data = {
        'ParentKey': ['A', 'B', 'A', 'C', 'B', 'D', 'E', 'F', 'A'],
        'ChildKey': ['X', 'Y', 'Z', 'W', 'V', 'U', 'T', 'S', 'R']
    }
    df = pd.DataFrame(data)

    # Test cases
    expected_non_unique_parentkey = 2  # 'A' appears 3 times, 'B' appears 2 times
    expected_unique_parentkey = 4      # 'C', 'D', 'E', 'F' appear 1 time each
    expected_non_unique_parent_child = 0  # No duplicate ParentKey-ChildKey pairs
    expected_unique_parent_child = 9      # All pairs are unique

    # Assertions
    all_tests_passed = True

    actual_non_unique_parentkey = Fcn_CountUnique(df, ['ParentKey'], count_non_unique=True)
    if actual_non_unique_parentkey != expected_non_unique_parentkey:
        all_tests_passed = False
        print(f"Test Case 1 Failed: Expected {expected_non_unique_parentkey}, but got {actual_non_unique_parentkey}")

    actual_unique_parentkey = Fcn_CountUnique(df, ['ParentKey'], count_non_unique=False)
    if actual_unique_parentkey != expected_unique_parentkey:
        all_tests_passed = False
        print(f"Test Case 2 Failed: Expected {expected_unique_parentkey}, but got {actual_unique_parentkey}")

    actual_non_unique_parent_child = Fcn_CountUnique(df, ['ParentKey', 'ChildKey'], count_non_unique=True)
    if actual_non_unique_parent_child != expected_non_unique_parent_child:
        all_tests_passed = False
        print(f"Test Case 3 Failed: Expected {expected_non_unique_parent_child}, but got {actual_non_unique_parent_child}")

    actual_unique_parent_child = Fcn_CountUnique(df, ['ParentKey', 'ChildKey'])
    if actual_unique_parent_child != expected_unique_parent_child:
        all_tests_passed = False
        print(f"Test Case 4 Failed: Expected {expected_unique_parent_child}, but got {actual_unique_parent_child}")

    if all_tests_passed:
        print("All test cases passed.")


def main():
    test_Fcn_CountUnique()


if __name__ == "__main__":
    main()

