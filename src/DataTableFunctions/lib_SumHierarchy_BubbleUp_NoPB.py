import pandas as pd
from lib_ColumnFcns import *
from lib_logging import *
from lib_treeFcns import *
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'

# Set pandas option to display all columns for debugging
pd.set_option('display.max_columns', None)
# Set the maximum display width
pd.set_option('display.width', 1000)


# **************************************
# * Private Helper Functions
# ************************************** 
# {{{
def replace_nulls_with_zeroes(data_table, columns):
    """_summary_
        Helper function: replace null values with zeroes

    Args:
        parentChildTable (_type_): _description_

    Raises:
        KeyError: _description_

    Returns:
        _type_: _description_
    """
    for col in columns:
        data_table[col].fillna(0, inplace=True)
    return data_table


def remove_circular_dependencies(parent_child_dt):
    """_summary_
        Helper function: assuming remove_circular_dependencies is defined elsewhere

    Args:
        parentChildTable (_type_): _description_

    Raises:
        KeyError: _description_

    Returns:
        _type_: _description_
    """
    with log_block("remove_circular_dependencies"):
        circular_loops_df = Fcn_FindCircularDependencies(parent_child_dt)
        num_of_circular_records = circular_loops_df.shape[0]

        log_debug(f"Circular loops DataFrame:\n{circular_loops_df}")

        if (num_of_circular_records > 0):
            # Ensure the DataFrame contains the expected columns
            if 'ParentKey' not in circular_loops_df.columns or 'ChildKey' not in circular_loops_df.columns:
                raise KeyError("The returned DataFrame from Fcn_FindCircularDependencies does not contain 'ParentKey' and 'ChildKey' columns.")

            # Remove duplicate Circular_Loops ParentKey-ChildKey pairs
            circular_loops_df = circular_loops_df.drop_duplicates(subset=['ParentKey', 'ChildKey'])

            # Create a combined list of ParentKey and ChildKey from df_unique
            listOfCircularNodes = pd.concat([circular_loops_df['ParentKey'], circular_loops_df['ChildKey']]).unique()

            # Remove rows from the original DataFrame where ParentKey or ChildKey are in listOfCircularNodes
            filtered_df = parent_child_dt[~parent_child_dt['ParentKey'].isin(listOfCircularNodes) &
                                        ~parent_child_dt['ChildKey'].isin(listOfCircularNodes)]
        else:
            filtered_df = parent_child_dt
        # end of if

    # end of with log_block
    return filtered_df


# ********************************************
def add_sum_columns(data_table, columns):
    """_summary_
        Helper function: add Parent Sum and Child Sum columns

    Args:
        data_table (_DataFrame_): _description_
        columns (_list_)

    Raises:
        none

    Returns:
        DataFrame: _description_
    """
    with log_block("add_sum_columns"):
        for col in columns:
            data_table[f"Parent Sum of {col}"] = 0
            data_table[f"Child Sum of {col}"] = 0

        # End for
    # End with log_block
    return data_table


# ********************************************
def sum_to_parent(nodes_to_process, columns_to_sum, prefix):
    """_summary_
        Helper function: add Parent Sum and Child Sum columns

    Args:
        nodes_to_process (_type_): _description_
        columns_to_sum
        prefix

    Raises:
        KeyError: _description_

    Returns:
        _type_: _description_
    """
    with log_block("sum_to_parent"):
        prefix_c = f"Child {prefix}"
        prefix_p = f"Parent {prefix}"
        sum_columns = [f"{prefix_p}{col}" for col in columns_to_sum]
        
        # Sum the child sums
        grouped = nodes_to_process.groupby('ParentKey')[[f"{prefix_c}{col}" for col in columns_to_sum]].sum().reset_index()
        grouped.columns = ['ParentKey'] + sum_columns
        
        # Merge the grouped sums back to the nodes to process
        nodes_processed = nodes_to_process.merge(grouped, on='ParentKey', suffixes=('', '_grouped'))
        
        # Add the original {col} values to the Parent Sum columns
        for col in columns_to_sum:
            nodes_processed[f"{prefix_p}{col}"] = nodes_processed[f"{prefix_p}{col}_grouped"] + nodes_processed[col]
        
        nodes_processed.drop(columns=[f"{col}_grouped" for col in sum_columns], inplace=True)

    # End with log_block
    return nodes_processed


# Helper function: select nodes to process
def select_nodes_to_process(state_table, loop_results):
    """_summary_

    Args:
        state_table (_type_): _description_
        loop_results (_type_): _description_

    Returns:
        _type_: _description_
    """
    with log_block("select_nodes_to_process"):
        nodes_table = state_table.copy()
        if not loop_results.empty:
            nodes_table.loc[nodes_table['ChildKey'].isin(loop_results['ParentKey']), 'ChildKey'] = None
        parent_keys_with_null_childkey = nodes_table[nodes_table['ChildKey'].isnull()]['ParentKey'].unique()
        parent_keys_with_non_null_childkey = nodes_table[nodes_table['ChildKey'].notnull()]['ParentKey'].unique()
        node_list = [key for key in parent_keys_with_null_childkey if key not in parent_keys_with_non_null_childkey]
        nodes_to_process = state_table[state_table['ParentKey'].isin(node_list)]

    # End with log_block
    return nodes_to_process


def update_state_table_with_results(state_table, loop_results, columns_to_sum):
    """_summary_
        Helper function: update state table with loop results

    Args:
        state_table (_type_): _description_
        loop_results (_type_): _description_
        columns_to_sum (_type_): _description_

    Returns:
        _type_: _description_
    """
    with log_block("update_state_table_with_results"):
        state_table = state_table[~state_table['ParentKey'].isin(loop_results['ParentKey'])]
        for col in columns_to_sum:
            for idx, row in loop_results.iterrows():
                state_table.loc[state_table['ChildKey'] == row['ParentKey'], f"Child Sum of {col}"] = row[f"Parent Sum of {col}"]

    # End with log_block
    return state_table

# **************************************
# * End of Private Helper Functions
# **************************************

# **************************************
# * Public Functions
# **************************************
def Fcn_SumHierarchy_BubbleUp(parentChild_DF, columns_to_sum, prefix="Sum of "):
    """_summary_

    Args:
        parentChild_DF (_type_): _description_
        columns_to_sum (_type_): _description_
        prefix (str, optional): _description_. Defaults to "Sum of ".

    Returns:
        _type_: _description_
    """
    with log_block("Fcn_SumHierarchy_BubbleUp"):
        # PreProcess
        # Step 1: Replace null values with zeroes
        state_table = replace_nulls_with_zeroes(parentChild_DF, columns_to_sum)

        # Step 2: Remove any nodes that are part of a circular dependency
        state_table = remove_circular_dependencies(state_table)

            # Step 3: Add "Parent Sum of {col}" and "Child Sum of {col}" columns with initial value of zero
        state_table = add_sum_columns(state_table, columns_to_sum)
        #print(f"state_table:\n{state_table}")

        # Step 4: Create empty results_table
        results_table = pd.DataFrame(columns=state_table.columns)
        #print(f"results_table:\n{results_table}")

        # Step 5: Create empty loop_results_table
        loop_results = pd.DataFrame(columns=state_table.columns)
        #print(f"loop_results:\n{loop_results}")

        while not state_table.empty:
            # Select nodes to process
            nodes_to_process = select_nodes_to_process(state_table, loop_results)
            #print(f"nodes_to_process:\n{nodes_to_process}")

            if nodes_to_process.empty:
                break

            # Sum children up to Parent and build up results
            loop_results = sum_to_parent(nodes_to_process, columns_to_sum, prefix)
            #print(f"loop_results:\n{loop_results}")

            # Update results
            results_table = pd.concat([results_table, loop_results])
            #print(f"results_table:\n{results_table}")

            # Update state table with results
            state_table = update_state_table_with_results(state_table, loop_results, columns_to_sum)
            # print(f"state_table:\n{state_table}")

        # End of while loop
    # End of with log_block
    return results_table


def Fcn_SumHierarchy_BubbleUp_SplitTables(parent_child_table, data_table, columns_to_sum, prefix="Sum of "):
    """_summary_

    Args:
        parent_child_table (_type_): _description_
        data_table (_type_): _description_
        columns_to_sum (_type_): _description_
        prefix (str, optional): _description_. Defaults to "Sum of ".

    Returns:
        _type_: _description_
    """
    with log_block("Starting sum_hierarchy_bubble_up_split_tables function."):
        data_table[columns_to_sum] = data_table[columns_to_sum].fillna(0)
        merged_df = pd.merge(parent_child_table, data_table, left_on='ParentKey', right_on='Issue key', how='left')
        merged_df = merged_df.drop(columns=['Issue key'])
        result = Fcn_SumHierarchy_BubbleUp(merged_df, columns_to_sum, prefix)
    # end of with log_block
    return result
# ************************************** 


# **************************************
# * Test Functions
# ************************************** 
def test_SumHierarchy_SmallTestCase_OneTable(testName):
    """_summary_

    Args:
        testName (_type_): _description_
    """
    columns_to_sum = ["EH", "RE", "TS"]
    prefix = "Sum of "

    # Initial data_table
    data = {
        'ParentKey': ['R1', 'R1', 'R2', 'R2', 'R1C1', 'R1C1', 'R1C2', 'R1C2', 'R2C1', 'R2C2', 'R1C1GC1', 'R1C1GC2', 'R1C2GC3', 'R1C2GC4', 'R2C1GC1'],
        'ChildKey': ['R1C1', 'R1C2', 'R2C1', 'R2C2', 'R1C1GC1', 'R1C1GC2', 'R1C2GC3', 'R1C2GC4', 'R2C1GC1', None, None, None, None, None, None],
        'EH': [1, 1, 4, 4, 11, 11, 14, 14, 17, 20, 100, 103, 106, 109, 112],
        'RE': [2, 2, 5, 5, 12, 12, 15, 15, 18, 21, 101, 104, 107, 110, 113],
        'TS': [3, 3, 6, 6, 13, 13, 16, 16, 19, 22, 102, 105, 108, 111, 114]
    }
    data_table = pd.DataFrame(data)
    test_results = Fcn_SumHierarchy_BubbleUp( data_table, columns_to_sum, prefix )
    print("****************************************************************")
    print(f"{testName}:\n{test_results}")


def test_SumHierarchy_SmallTestCase_TwoTables(testName):
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
    print("****************************************************************")
    print(f"{testName}:\n{test_results}")

# ************************************** 

# **************************************
# * Main Function
# ************************************** 
def main():
    test_SumHierarchy_SmallTestCase_OneTable("OneTable")
    test_SumHierarchy_SmallTestCase_TwoTables("TwoTables")


if __name__ == "__main__":
    main()
