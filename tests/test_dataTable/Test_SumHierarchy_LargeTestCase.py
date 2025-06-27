#!/usr/bin/env python3

import pandas as pd
import os 
from lib_SumHierarchy_BubbleUp import *
from lib_logging import *

# Configure the logger
setup_logging(level=logging.DEBUG)
pd.set_option('display.max_columns', None)
# Set the maximum display width
pd.set_option('display.width', 1000)

OutputFile="TestResults_Large.csv"
DataDir="/Users/shawnhillis/bin/python/DataTableFunctions/"
#ParentChildFile="Test_LargeParentChildTable_20240731.csv"
#DataFile="Test_LargeDataTable_20240731.csv"
ParentChildFile="ParentChildRealWorldSample_20240810_v01.csv"
DataFile="DataTableRealWorldSample_20240810_v01.csv"

def test_hierarchical_sum():
    log_info("Starting test_hierarchical_sum.")
    dataTable = pd.read_csv(DataDir + DataFile, encoding='ISO-8859-1')
    parentChildTable = pd.read_csv(DataDir + ParentChildFile, encoding='ISO-8859-1')

    columns_to_sum_up = ["Estimated Hours", "Remaining Estimate", "Epic Current Estimate", "Epic Original Estimate", 
        "Original Estimate", "Hour Budget", "Time Spent"]
    prefix = "Sum of "

    final_results = Fcn_SumHierarchy_BubbleUp_SplitTables( parentChildTable, dataTable, columns_to_sum_up, prefix )
    #log_debug(f"Final Result:\n{final_result.head()}")
    output_full_path = os.path.join(DataDir, OutputFile)
    final_results.to_csv(output_full_path, index=False)


if __name__ == "__main__":
    test_hierarchical_sum()

