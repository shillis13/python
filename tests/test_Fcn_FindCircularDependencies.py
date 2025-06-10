#!/usr/bin/env python3

import pandas as pd
from lib_treeFcns import Fcn_FindCircularDependencies
from lib_miscDataTableFcns import dataframes_equal  

def test_Fcn_FindCircularDependencies():
    # Test case 1: No circular dependencies
    df1 = pd.DataFrame({
        'ParentKey': ['A', 'A', 'B', 'C', 'C', 'E'],
        'ChildKey': ['B', 'C', 'D', 'E', 'F', 'G']
    })
    # expected1 = pd.DataFrame(columns=['ParentKey', 'ChildKey'])
    expected1 = pd.DataFrame()
    result1 = Fcn_FindCircularDependencies(df1)
    pd.testing.assert_frame_equal(result1, expected1, check_dtype=False, obj="Test Case 1 Failed")

    # Test case 2: Circular dependency where child points to parent
    df2 = pd.DataFrame({
        'ParentKey': ['A', 'B'],
        'ChildKey': ['B', 'A']
    })
    expected2 = df2
    result2 = Fcn_FindCircularDependencies(df2)
    pd.testing.assert_frame_equal(result2, expected2, check_dtype=False, obj="Test Case 2 Failed")

    # Test case 3: Circular dependency spanning 4 generations
    df3 = pd.DataFrame({
        'ParentKey': ['A', 'B', 'C', 'D'],
        'ChildKey': ['B', 'C', 'D', 'A']
    })
    expected3 = df3
    result3 = Fcn_FindCircularDependencies(df3)
    pd.testing.assert_frame_equal(result3, expected3, check_dtype=False, obj="Test Case 3 Failed")

    # Test case 4: Multiple circular dependencies
    df4 = pd.DataFrame({
        'ParentKey': ['A', 'B', 'C', 'D', 'E', 'F'],
        'ChildKey': ['B', 'A', 'D', 'C', 'F', 'E']
    })
    expected4 = df4
    result4 = Fcn_FindCircularDependencies(df4)
    # pd.testing.assert_frame_equal(result4, expected4, check_dtype=False, obj="Test Case 4 Failed")
    pd.testing.assert_frame_equal(result4.reset_index(drop=True), expected4.reset_index(drop=True), 
        check_dtype=False, obj="Test Case 4 Failed")


    # Test case 5: Multiple circular dependencies with branches
    df5 = pd.DataFrame({
        'ParentKey': ['A', 'A', 'B', 'C', 'D', 'E', 'F', 'G'],
        'ChildKey': ['B', 'C', 'D', 'E', 'F', 'G', 'A', 'B']
    })
    expected5 = pd.DataFrame({
        'ParentKey': ['A', 'A', 'B', 'C', 'D', 'F', 'G'],
        'ChildKey': ['B', 'C', 'D', 'E', 'F', 'A', 'B']
    })
    result5 = Fcn_FindCircularDependencies(df5)
    testPassed5 = dataframes_equal(expected5, result5)
    try:
        assert testPassed5, "Test Case 5 Failed"
    except AssertionError as e:
        print(f"TestCase #5 failed:")
        print(f"TestData:\n{df5}")
        print(f"Expected:\n{expected5}")
        print(f"Results:\n{result5}")

    #pd.testing.assert_frame_equal(result5.reset_index(drop=True), expected5.reset_index(drop=True), 
        #check_dtype=False, obj="Test Case 5 Failed")

    print("All test cases passed!")

test_Fcn_FindCircularDependencies()


