""" 
File: lib_SumHierarchy_BubbleUp.py
"""
import warnings
import pandas as pd
from lib_logging import log_block, log_debug, log_info
from lib_treeFcns import Fcn_FindCircularDependencies
from lib_progressBar import progress_bar, ProgressBarContext, enable_progress_bars, disable_progress_bars
from lib_outputColors import print_colored, print_help_color, colored

warnings.filterwarnings("ignore", category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

# Set pandas option to display all columns for debugging
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)


# **************************************
# * Private Helper Functions
# **************************************
def replace_nulls_with_zeroes(data_table, columns):
    """
    Replace any null values in the specified columns with zeroes.

    Args:
        data_table (pd.DataFrame): The DataFrame containing the data.
        columns (list): List of columns where null values need to be replaced.

    Returns:
        pd.DataFrame: The DataFrame with null values replaced by zeroes.
    """
    for col in columns:
        data_table[col].fillna(0, inplace=True)
    return data_table


@progress_bar(total=10, desc="Remove Circular Dependencies")
def remove_circular_dependencies(parent_child_dt):
    """
    Remove rows that are part of a circular dependency to prevent infinite loops.

    Args:
        parent_child_dt (pd.DataFrame): The DataFrame containing parent-child relationships.

    Raises:
        KeyError: If 'ParentKey' or 'ChildKey' columns are missing.

    Returns:
        pd.DataFrame: The DataFrame with circular dependencies removed.
    """
    with log_block("remove_circular_dependencies"):
        circular_loops_df = Fcn_FindCircularDependencies(parent_child_dt)
        num_of_circular_records = circular_loops_df.shape[0]

        log_debug(f"Circular loops DataFrame:\n{circular_loops_df}")

        if num_of_circular_records > 0:
            if 'ParentKey' not in circular_loops_df.columns or 'ChildKey' not in circular_loops_df.columns:
                raise KeyError("The returned DataFrame from Fcn_FindCircularDependencies does not contain 'ParentKey' and 'ChildKey' columns.")

            circular_loops_df = circular_loops_df.drop_duplicates(subset=['ParentKey', 'ChildKey'])

            listOfCircularNodes = pd.concat([circular_loops_df['ParentKey'], circular_loops_df['ChildKey']]).unique()

            log_info(f"Removing {len(listOfCircularNodes)} nodes that are part of circular dependencies")
            filtered_df = parent_child_dt[~parent_child_dt['ParentKey'].isin(listOfCircularNodes) &
                                        ~parent_child_dt['ChildKey'].isin(listOfCircularNodes)]
        else:
            filtered_df = parent_child_dt
    return filtered_df
    

def add_sum_columns(data_table, columns):
    """
    Add new columns for storing the sum of values from parent and child nodes.

    Args:
        data_table (pd.DataFrame): The DataFrame containing the data.
        columns (list): List of columns to add sum columns for.

    Returns:
        pd.DataFrame: The DataFrame with new sum columns added.
    """
    with log_block("add_sum_columns"):
        for col in columns:
            data_table[f"Parent Sum of {col}"] = 0
            data_table[f"Child Sum of {col}"] = 0
    return data_table


@progress_bar(total=10, desc="Sum Children to Parent")
def sum_to_parent(nodes_to_process, columns_to_sum, prefix):
    """
    Sum the values from child nodes and add them to the corresponding parent nodes.

    Args:
        nodes_to_process (pd.DataFrame): The DataFrame containing the nodes to process.
        columns_to_sum (list): List of columns to sum values for.
        prefix (str): Prefix for the sum columns.

    Raises:
        KeyError: If columns are missing.

    Returns:
        pd.DataFrame: The DataFrame with summed values added to parent nodes.
    """
    with log_block("sum_to_parent"):
        prefix_c = f"Child {prefix}"
        prefix_p = f"Parent {prefix}"
        sum_columns = [f"{prefix_p}{col}" for col in columns_to_sum]

        grouped = nodes_to_process.groupby('ParentKey')[[f"{prefix_c}{col}" for col in columns_to_sum]].sum().reset_index()
        grouped.columns = ['ParentKey'] + sum_columns

        nodes_processed = nodes_to_process.merge(grouped, on='ParentKey', suffixes=('', '_grouped'))

        for col in columns_to_sum:
            nodes_processed[f"{prefix_p}{col}"] = nodes_processed[f"{prefix_p}{col}_grouped"] + nodes_processed[col]

        nodes_processed.drop(columns=[f"{col}_grouped" for col in sum_columns], inplace=True)
    return nodes_processed

@progress_bar(total=10, desc="Select Nodes to Process")
def select_nodes_to_process(state_table, loop_results):
    """
    Select the nodes that need to be processed in the current loop iteration.

    Args:
        state_table (pd.DataFrame): The DataFrame containing the current state of nodes.
        loop_results (pd.DataFrame): The DataFrame containing results from the last loop iteration.

    Returns:
        pd.DataFrame: The DataFrame with nodes to process in the current loop iteration.
    """
    with log_block("select_nodes_to_process"):
        nodes_table = state_table.copy()
        if not loop_results.empty:
            nodes_table.loc[nodes_table['ChildKey'].isin(loop_results['ParentKey']), 'ChildKey'] = None
        parent_keys_with_null_childkey = nodes_table[nodes_table['ChildKey'].isnull()]['ParentKey'].unique()
        parent_keys_with_non_null_childkey = nodes_table[nodes_table['ChildKey'].notnull()]['ParentKey'].unique()
        node_list = [key for key in parent_keys_with_null_childkey if key not in parent_keys_with_non_null_childkey]
        nodes_to_process = state_table[state_table['ParentKey'].isin(node_list)]
    return nodes_to_process

@progress_bar(total=10, desc="Update State Table")
def update_state_table_with_results(state_table, loop_results, columns_to_sum):
    """
    Update the state table with the results from the current loop iteration.

    Args:
        state_table (pd.DataFrame): The DataFrame containing the current state of nodes.
        loop_results (pd.DataFrame): The DataFrame containing results from the current loop iteration.
        columns_to_sum (list): List of columns to update sum values for.

    Returns:
        pd.DataFrame: The updated state table.
    """
    with log_block("update_state_table_with_results"):
        state_table = state_table[~state_table['ParentKey'].isin(loop_results['ParentKey'])]
        for col in columns_to_sum:
            # for idx, row in loop_results.iterrows():
            #for row in loop_results.iterrows():
                #state_table.loc[state_table['ChildKey'] == row['ParentKey'], f"Child Sum of {col}"] = row[f"Parent Sum of {col}"]
            for idx, row in loop_results.iterrows():
                state_table.loc[state_table['ChildKey'] == row['ParentKey'], f"Child Sum of {col}"] = row[f"Parent Sum of {col}"]
    return state_table


# **************************************
# * End of Private Helper Functions
# **************************************

# **************************************
# * Public Functions
# **************************************

@progress_bar(total=100, desc="Fcn_SumHierarchy_BubbleUp")
def Fcn_SumHierarchy_BubbleUp(parentChild_DF, columns_to_sum, prefix="Sum of ", total=None):
    """
    Perform a hierarchical summation of values from child nodes to parent nodes.

    Args:
        parentChild_DF (pd.DataFrame): The DataFrame containing parent-child relationships and values.
        columns_to_sum (list): List of columns to sum values for.
        prefix (str, optional): Prefix for the sum columns. Defaults to "Sum of ".
        total (int, optional): Total number of iterations for progress bar. Defaults to None.

    Returns:
        pd.DataFrame: The DataFrame with summed values bubbled up from child nodes to parent nodes.
    """
    with log_block("Fcn_SumHierarchy_BubbleUp"):
        # PreProcess
        # Step 1: Replace null values with zeroes
        state_table = replace_nulls_with_zeroes(parentChild_DF, columns_to_sum)

        # Step 2: Remove any nodes that are part of a circular dependency
        state_table = remove_circular_dependencies(state_table)

        # Step 3: Add "Parent Sum of {col}" and "Child Sum of {col}" columns with initial value of zero
        state_table = add_sum_columns(state_table, columns_to_sum)

        # Step 4: Create empty results_table
        results_table = pd.DataFrame(columns=state_table.columns)

        # Step 5: Create empty loop_results_table
        loop_results = pd.DataFrame(columns=state_table.columns)

        # Step 6: Loop until state_table is empty
        with ProgressBarContext(total=len(state_table)) as pbar:
            while not state_table.empty:
                # Select nodes to process
                nodes_to_process = select_nodes_to_process(state_table, loop_results)
                if nodes_to_process.empty:
                    break

                # Sum children up to Parent and build up results
                loop_results = sum_to_parent(nodes_to_process, columns_to_sum, prefix)

                # Update results
                results_table = pd.concat([results_table, loop_results])

                # Update state table with results
                state_table = update_state_table_with_results(state_table, loop_results, columns_to_sum)

                # Update progress bar
                if pbar:
                    pbar.update(loop_results.shape[0])

    return results_table

@progress_bar(total=100, desc="Fcn_SumHierarchy_BubbleUp_SplitTables")
def Fcn_SumHierarchy_BubbleUp_SplitTables(parent_child_table, data_table, columns_to_sum, prefix="Sum of "):
    """
    Merge parent-child relationships with data and perform hierarchical summation.

    Args:
        parent_child_table (pd.DataFrame): The DataFrame containing parent-child relationships.
        data_table (pd.DataFrame): The DataFrame containing values to be summed.
        columns_to_sum (list): List of columns to sum values for.
        prefix (str, optional): Prefix for the sum columns. Defaults to "Sum of ".

    Returns:
        pd.DataFrame: The DataFrame with summed values bubbled up from child nodes to parent nodes.
    """
    with log_block("Fcn_SumHierarchy_BubbleUp_SplitTables"):
        data_table[columns_to_sum] = data_table[columns_to_sum].fillna(0)
        merged_df = pd.merge(parent_child_table, data_table, left_on='ParentKey', right_on='Issue key', how='left')
        merged_df = merged_df.drop(columns=['Issue key'])
        result = Fcn_SumHierarchy_BubbleUp(merged_df, columns_to_sum, prefix)
    return result

# **************************************
# * Test Functions
# **************************************
def test_SumHierarchy_SmallTestCase_OneTable(testName):
    """
    Test case for hierarchical summation using a single table.

    Args:
        testName (str): The name of the test case.
    """
    columns_to_sum = ["EH", "RE", "TS"]
    prefix = "Sum of "

    data = {
        'ParentKey': ['R1', 'R1', 'R2', 'R2', 'R1C1', 'R1C1', 'R1C2', 'R1C2', 'R2C1', 'R2C2', 'R1C1GC1', 'R1C1GC2', 'R1C2GC3', 'R1C2GC4', 'R2C1GC1'],
        'ChildKey': ['R1C1', 'R1C2', 'R2C1', 'R2C2', 'R1C1GC1', 'R1C1GC2', 'R1C2GC3', 'R1C2GC4', 'R2C1GC1', None, None, None, None, None, None],
        'EH': [1, 1, 4, 4, 11, 11, 14, 14, 17, 20, 100, 103, 106, 109, 112],
        'RE': [2, 2, 5, 5, 12, 12, 15, 15, 18, 21, 101, 104, 107, 110, 113],
        'TS': [3, 3, 6, 6, 13, 13, 16, 16, 19, 22, 102, 105, 108, 111, 114]
    }
    data_table = pd.DataFrame(data)
    test_results = Fcn_SumHierarchy_BubbleUp(data_table, columns_to_sum, prefix, total=len(data_table))
    print(f"\n****************************************************************")
    print(f"{testName}:\n{test_results}")

def test_SumHierarchy_SmallTestCase_TwoTables(testName):
    """
    Test case for hierarchical summation using two separate tables.

    Args:
        testName (str): The name of the test case.
    """
    parent_child_hierarchy_simple = pd.DataFrame({
        'ParentKey': ["R1", "R1", "R2", "R2", "R1C1", "R1C1", "R1C2", "R1C2", "R2C1", "R2C2", "R1C1GC1", "R1C1GC2", "R1C2GC3", "R1C2GC4", "R2C1GC1"],
        'ChildKey': ["R1C1", "R1C2", "R2C1", "R2C2", "R1C1GC1", "R1C1GC2", "R1C2GC3", "R1C2GC4", "R2C1GC1", None, None, None, None, None, None]
    })

    sum_fcn_test_data = pd.DataFrame({
        'Issue key': ["R1", "R2", "R1C1", "R1C2", "R2C1", "R2C2", "R1C1GC1", "R1C1GC2", "R1C2GC3", "R1C2GC4", "R2C1GC1"],
        'EstimatedHours': [1, 4, 11, 14, 17, 20, 100, 103, 106, 109, 112],
        'RemainingEstimate': [2, 5, 12, 15, 18, 21, 101, 104, 107, 110, 113],
        'TimeSpent': [3, 6, 13, 16, 19, 22, 102, 105, 108, 111, 114]
    })

    columns_to_sum_up_names = ["EstimatedHours", "RemainingEstimate", "TimeSpent"]
    prefix = "Sum of "

    test_results = Fcn_SumHierarchy_BubbleUp_SplitTables(parent_child_hierarchy_simple, sum_fcn_test_data, columns_to_sum_up_names, prefix)
    print("\n****************************************************************")
    print(f"{testName}:\n{test_results}")

# **************************************
# * Main Function
# **************************************
def main():
    ''' I hate these docstring warnings'''
    enable_progress_bars()
    test_SumHierarchy_SmallTestCase_OneTable("OneTable")
    test_SumHierarchy_SmallTestCase_TwoTables("TwoTables")
    disable_progress_bars()

if __name__ == "__main__":
    main()
