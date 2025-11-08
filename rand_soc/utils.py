from math import inf
import random
from typing import Any, Callable, Iterable, List, Optional
import networkx as nx


def randbool():
    return random.choice([True, False])


def randintwidth(width):
    return random.randint(0, 2**width - 1)


def all_ones(width):
    return 2**width - 1


def pull_from_list(lst, new_list, fcn):
    lst_copy = []
    for item in lst:
        (new_list if fcn(item) else lst_copy).append(item)
    lst[:] = lst_copy


def divide_into_groups(num_items, num_groups):
    # Calculate the base size of each group
    base_size = num_items // num_groups
    remainder = num_items % num_groups

    groups = [base_size] * num_groups

    # Distribute the remainder across the first few groups
    for i in range(remainder):
        groups[i] += 1

    return groups


def min_subset_sum_by_key(
    items: Iterable[Any],
    target: int,
    key: Callable[[Any], int],
) -> Optional[List[Any]]:
    """
    Return a minimal-cardinality subset of `items` whose key-summed value equals `target`.

    Each item is unique by index. Only non-negative integer key values are supported.

    Parameters
    ----------
    items : Iterable[Any]
        Input objects.
    target : int
        Desired sum. Must be >= 0.
    key : Callable[[Any], int]
        Function mapping an object to a non-negative integer.

    Returns
    -------
    list[Any] | None
        A list of objects that sum to `target` with the fewest elements, or None if impossible.

    Complexity
    ----------
    Time  : O(n * target)
    Space : O(target)
    """

    # Materialize items and extract validated integer values
    objs = list(items)
    vals = []
    for o in objs:
        v = key(o)
        if not isinstance(v, int) or v < 0:
            raise ValueError("key(obj) must return a non-negative integer.")
        vals.append(v)

    # DP arrays:
    # dp[s]   = minimal count of items to reach sum s
    # prev[s] = (previous_sum, index_of_item_used) for reconstruction
    dp = [inf] * (target + 1)
    prev = [None] * (target + 1)
    dp[0] = 0

    # 0-1 knap-style transition. Iterate sums downward to avoid reusing an item.
    for i, a in enumerate(vals):
        if a > target:
            continue
        for s in range(target - a, -1, -1):
            if dp[s] + 1 < dp[s + a]:
                dp[s + a] = dp[s] + 1
                prev[s + a] = (s, i)

    if dp[target] is inf:
        return None

    # Reconstruct chosen objects with minimal count
    res, s = [], target
    while s:
        ps, i = prev[s]
        res.append(objs[i])
        s = ps
    res.reverse()
    return res


def sink_scc_representatives(G):
    """
    Return one representative node from each sink SCC in a directed graph G.

    If you add edges from each of these representatives to a new node t,
    then every node in G will be able to reach t through the directed edges.

    Parameters
    ----------
    G : nx.DiGraph
        The directed graph. Nodes can be any hashable Python objects.

    Returns
    -------
    reps : list
        One node from each sink SCC.
    """

    # Step 1: Find all strongly connected components (SCCs).
    # Each SCC is a set of nodes where every node can reach every other.
    sccs = list(nx.strongly_connected_components(G))

    # Step 2: Build a map from node -> component index.
    # This lets us know which SCC each node belongs to.
    comp_id = {}
    for i, comp in enumerate(sccs):
        for v in comp:
            comp_id[v] = i

    # Step 3: Initialize an outdegree counter for each SCC.
    # We will later count edges that go from one SCC to another.
    outdeg = [0] * len(sccs)

    # Step 4: Examine all edges in G.
    # For every edge u → v that crosses between two different SCCs,
    # increment the outdegree of the source SCC.
    for u, v in G.edges():
        cu, cv = comp_id[u], comp_id[v]
        if cu != cv:
            outdeg[cu] += 1

    # Step 5: Identify sink SCCs (those with no outgoing edges).
    # outdeg[i] == 0 means SCC[i] is a sink in the condensation DAG.
    # Pick one representative node from each sink SCC.
    reps = [next(iter(comp)) for i, comp in enumerate(sccs) if outdeg[i] == 0]

    return reps
