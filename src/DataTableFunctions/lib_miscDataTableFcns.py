import pandas as pd
import numpy as np

"""
Compare two DataFrames for equality, with options to ignore index, row order, and column order.

This function compares the content of two Pandas DataFrames to determine if they are equal.
It provides options to ignore the index, the order of rows, and the order of columns, allowing
for a flexible comparison based purely on the data within the DataFrames.

Parameters:
-----------
df1 : pandas.DataFrame
    The first DataFrame to compare.
df2 : pandas.DataFrame
    The second DataFrame to compare.
ignoreIndex : bool, optional (default=True)
    If True, the function will ignore the index and compare only the data.
ignoreRowOrder : bool, optional (default=True)
    If True, the function will ignore the order of rows when comparing the DataFrames.
ignoreColumnOrder : bool, optional (default=True)
    If True, the function will ignore the order of columns when comparing the DataFrames.

Returns:
--------
bool
    True if the DataFrames are considered equal based on the provided options; False otherwise.

Examples:
---------
>>> df1 = pd.DataFrame({
...     'A': [3, 2, 1],
...     'B': [6, 5, 4]
... })
>>> df2 = pd.DataFrame({
...     'A': [1, 2, 3],
...     'B': [4, 5, 6]
... })
>>> dataframes_equal(df1, df2)
True

>>> df3 = pd.DataFrame({
...     'A': [3, 2, 1],
...     'B': [6, 5, 4]
... }, index=[0, 1, 2])
>>> df4 = pd.DataFrame({
...     'A': [3, 2, 1],
...     'B': [6, 5, 4]
... }, index=[2, 1, 0])
>>> dataframes_equal(df3, df4, ignoreIndex=False)
False

>>> df5 = pd.DataFrame({
...     'A': [1, 2, 3],
...     'B': [4, 5, 6]
... })
>>> df6 = pd.DataFrame({
...     'B': [4, 5, 6],
...     'A': [1, 2, 3]
... })
>>> dataframes_equal(df5, df6, ignoreColumnOrder=True)
True
"""


def dataframes_equal(
    df1, df2, ignoreIndex=True, ignoreRowOrder=True, ignoreColumnOrder=True
):
    # If ignoring index, reset both DataFrames' indexes
    if ignoreIndex:
        df1 = df1.reset_index(drop=True)
        df2 = df2.reset_index(drop=True)
    else:
        # If not ignoring index, make sure indexes are identical
        if not df1.index.equals(df2.index):
            return False

    # If ignoring column order, sort both DataFrames' columns
    if ignoreColumnOrder:
        df1 = df1[sorted(df1.columns)]
        df2 = df2[sorted(df2.columns)]

    # If ignoring row order, sort both DataFrames by all columns
    if ignoreRowOrder:
        df1 = df1.sort_values(by=df1.columns.tolist()).reset_index(drop=True)
        df2 = df2.sort_values(by=df2.columns.tolist()).reset_index(drop=True)

    # Use equals() to compare the data
    return df1.equals(df2)


# Example usage:
# df1 = pd.DataFrame({'A': [3, 2, 1], 'B': [6, 5, 4]})
# df2 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
# print(dataframes_equal(df1, df2))  # Output: True
