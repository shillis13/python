#!/usr/bin/env python3

import pandas as pd
from pathlib import Path

from lib_SumHierarchy_BubbleUp import *
from lib_logging import *

# Configure the logger
setup_logging(level=logging.DEBUG)
pd.set_option('display.max_columns', None)
# Set the maximum display width
pd.set_option('display.width', 1000)

# Determine the directory that contains this test so sample data can be loaded
# relative to the repository rather than using hard coded absolute paths.
DATA_DIR = Path(__file__).parent
OUTPUT_FILE = "TestResults_Large.csv"
#ParentChildFile="Test_LargeParentChildTable_20240731.csv"
#DataFile="Test_LargeDataTable_20240731.csv"
PARENT_CHILD_FILE = "ParentChildRealWorldSample_20240810_v01.csv"
DATA_FILE = "DataTableRealWorldSample_20240810_v01.csv"

def test_hierarchical_sum():
    log_info("Starting test_hierarchical_sum.")
    dataTable = pd.read_csv(DATA_DIR / DATA_FILE, encoding='ISO-8859-1')
    parentChildTable = pd.read_csv(DATA_DIR / PARENT_CHILD_FILE, encoding='ISO-8859-1')

    columns_to_sum_up = ["Estimated Hours", "Remaining Estimate", "Epic Current Estimate", "Epic Original Estimate", 
        "Original Estimate", "Hour Budget", "Time Spent"]
    prefix = "Sum of "

    final_results = Fcn_SumHierarchy_BubbleUp_SplitTables( parentChildTable, dataTable, columns_to_sum_up, prefix )
    #log_debug(f"Final Result:\n{final_result.head()}")
    output_full_path = DATA_DIR / OUTPUT_FILE
    final_results.to_csv(output_full_path, index=False)


if __name__ == "__main__":
    test_hierarchical_sum()

