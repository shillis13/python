"""
File: lib_treeFcns.py
"""

import pandas as pd

pd.options.mode.chained_assignment = None  # default='warn'

"""
********************************************************************
Function Name: Fcn_FindRootNodes
Description: This function identifies the root nodes in a hierarchical structure given a table with parent-child relationships.
Parameters:
- parent_child_table (pd.DataFrame): The input table containing the parent-child relationships.
- parent_key (str, optional): The name of the column representing the parent keys. Defaults to "ParentKey".
- child_key (str, optional): The name of the column representing the child keys. Defaults to "ChildKey".
Returns: list - A list of root nodes.
********************************************************************
"""


def Fcn_FindRootNodes(parent_child_table, parent_key="ParentKey", child_key="ChildKey"):
    # Extract Parent and Child columns
    parent_keys = parent_child_table[parent_key].dropna().unique()
    child_keys = parent_child_table[child_key].dropna().unique()

    # Identify root nodes
    root_nodes = list(set(parent_keys) - set(child_keys))

    return root_nodes


# Example usage
"""
data = {
    'ParentKey': ["A", "A", "B", "C", "C", "E"],
    'ChildKey': ["B", "C", "D", "E", "F", "G"]
}
parent_child_table = pd.DataFrame(data)
root_nodes = find_root_nodes(parent_child_table)
print(root_nodes)  # Output: ['A']
"""


"""
********************************************************************
Function Name: Fcn_CalculateMaxDepth
Description: This function calculates the maximum depth of hierarchical trees in the ParentChildTable.
Parameters:
- parent_child_table (pd.DataFrame): The input table containing the parent-child relationships.
- parent_key (str, optional): The name of the column representing the parent keys. Defaults to "ParentKey".
- child_key (str, optional): The name of the column representing the child keys. Defaults to "ChildKey".
Returns: int - The maximum depth of the hierarchical trees.
********************************************************************
"""


def Fcn_CalculateMaxDepth(
    parent_child_table, parent_key="ParentKey", child_key="ChildKey"
):
    def calculate_depth(node, depth=0):
        children = (
            parent_child_table[parent_child_table[parent_key] == node][child_key]
            .dropna()
            .unique()
        )
        if len(children) == 0:
            return depth
        else:
            return max([calculate_depth(child, depth + 1) for child in children])

    # Find all root nodes
    root_nodes = Fcn_FindRootNodes(parent_child_table, parent_key, child_key)

    # Calculate depths for all root nodes
    depths = [calculate_depth(root) for root in root_nodes]

    # Get the maximum depth
    max_depth = max(depths) if depths else 0

    return max_depth


# Example usage
"""
data = {
    'ParentKey': ["A", "A", "B", "C", "C", "E"],
    'ChildKey': ["B", "C", "D", "E", "F", "G"]
}
parent_child_table = pd.DataFrame(data)
max_depth = calculate_max_depth(parent_child_table)
print(max_depth)  # Output: 4
"""


"""
Identifies circular dependencies in a DataFrame representing a parent-child relationship graph.

This function takes a DataFrame with columns 'ParentKey' and 'ChildKey' and returns a new
DataFrame that contains all the circular dependencies found in the input. Each row in the
returned DataFrame represents a direct parent-child relationship that is part of a circular path.

Parameters:
-----------
df : pandas.DataFrame
    A DataFrame containing the parent-child relationships. It must have two columns:
    - 'ParentKey': The parent node in the relationship.
    - 'ChildKey': The child node in the relationship.

Returns:
--------
pandas.DataFrame
    A DataFrame containing the circular dependencies. The DataFrame will have two columns:
    - 'ParentKey': The parent node in the circular path.
    - 'ChildKey': The child node in the circular path.

Example:
--------
>>> data = {
...     'ParentKey': ['A', 'A', 'B', 'C', 'D', 'E', 'F', 'G'],
...     'ChildKey': ['B', 'C', 'D', 'E', 'F', 'G', 'A', 'B']
... }
>>> df = pd.DataFrame(data)
>>> Fcn_FindCircularDependencies(df)
  ParentKey ChildKey
0         A        B
1         B        D
2         D        F
3         F        A
4         A        C
5         C        E
6         E        G
7         G        B

In this example, the function identifies multiple circular dependencies:
- A -> B -> D -> F -> A
- A -> C -> E -> G -> B
"""


def Fcn_FindCircularDependencies(df):
    def find_circular_paths(graph, start_node, visited=None, path=None):
        if visited is None:
            visited = set()
        if path is None:
            path = []

        visited.add(start_node)
        path.append(start_node)

        circular_paths = []

        for neighbor in graph.get(start_node, []):
            if neighbor not in visited:
                circular_paths.extend(
                    find_circular_paths(graph, neighbor, visited.copy(), path.copy())
                )
            elif neighbor in path:
                cycle_start_index = path.index(neighbor)
                circular_paths.append(path[cycle_start_index:] + [neighbor])

        return circular_paths

    graph = {}
    for _, row in df.iterrows():
        parent = row["ParentKey"]
        child = row["ChildKey"]
        if parent not in graph:
            graph[parent] = []
        graph[parent].append(child)

    all_circular_paths = []
    for node in graph:
        all_circular_paths.extend(find_circular_paths(graph, node))

    circular_df_rows = []
    for path in all_circular_paths:
        for i in range(len(path) - 1):
            circular_df_rows.append({"ParentKey": path[i], "ChildKey": path[i + 1]})

    circular_df = pd.DataFrame(circular_df_rows)
    circular_df = circular_df.drop_duplicates(subset=["ParentKey", "ChildKey"])

    return circular_df


def Fcn_FindCircularDependencies2(df):
    def find_cycles(df):
        graph = df.groupby("ParentKey")["ChildKey"].apply(list).to_dict()
        visited = set()
        stack = set()
        circular_nodes = set()

        def visit(node):
            if node in visited:
                return
            if node in stack:
                circular_nodes.update(stack)
                return
            stack.add(node)
            for neighbor in graph.get(node, []):
                visit(neighbor)
            stack.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

        return circular_nodes

    circular_nodes = find_cycles(df)
    return df[
        df["ParentKey"].isin(circular_nodes) | df["ChildKey"].isin(circular_nodes)
    ]


"""
# Example usage
ParentChildTable = pd.DataFrame({
    'ParentKey': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
    'ChildKey': ['B', 'C', 'D', 'A', 'F', 'G', 'H', 'E']  # This introduces a cycle A -> B -> C -> D -> A and E -> F -> G -> H -> E
})

circular_dependencies = Fcn_FindCircularDependencies(ParentChildTable)
print(circular_dependencies)
"""
