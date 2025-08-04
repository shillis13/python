import os
import sys
import pytest
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from DataTableFunctions.lib_miscDataTableFcns import dataframes_equal

def test_identical_dataframes():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    assert dataframes_equal(df1, df2) == True

def test_different_dataframes():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [3, 2, 1], 'B': [6, 5, 4]})
    assert dataframes_equal(df1, df2, ignoreRowOrder=True) == True

def test_different_column_order():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'B': [4, 5, 6], 'A': [1, 2, 3]})
    assert dataframes_equal(df1, df2, ignoreColumnOrder=True) == True

def test_different_row_order():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [3, 1, 2], 'B': [6, 4, 5]})
    assert dataframes_equal(df1, df2, ignoreRowOrder=True) == True

def test_different_indexes():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}, index=[0, 1, 2])
    df2 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}, index=[2, 1, 0])
    assert dataframes_equal(df1, df2, ignoreIndex=True) == True

def test_different_indexes_no_ignore():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}, index=[0, 1, 2])
    df2 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}, index=[2, 1, 0])
    assert dataframes_equal(df1, df2, ignoreIndex=False) == False

def test_nan_handling():
    df1 = pd.DataFrame({'A': [1, 2, None], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [1, 2, None], 'B': [4, 5, 6]})
    assert dataframes_equal(df1, df2) == True

def test_nan_handling_different_positions():
    df1 = pd.DataFrame({'A': [1, None, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [1, 2, None], 'B': [4, 5, 6]})
    assert dataframes_equal(df1, df2) == False

def test_empty_dataframes():
    df1 = pd.DataFrame({'A': [], 'B': []})
    df2 = pd.DataFrame({'A': [], 'B': []})
    assert dataframes_equal(df1, df2) == True

def test_empty_vs_nonempty_dataframes():
    df1 = pd.DataFrame({'A': [], 'B': []})
    df2 = pd.DataFrame({'A': [1], 'B': [4]})
    assert dataframes_equal(df1, df2) == False

def test_subset_columns():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'A': [1, 2, 3]})
    assert dataframes_equal(df1, df2) == False

def test_column_order_and_row_order_ignored():
    df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    df2 = pd.DataFrame({'B': [6, 4, 5], 'A': [3, 1, 2]})
    assert dataframes_equal(df1, df2, ignoreRowOrder=True, ignoreColumnOrder=True) == True

if __name__ == "__main__":
    pytest.main()

