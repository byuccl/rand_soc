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


def randpuncture(input_rate, output_rate):
    """Random valid puncture-code pair for the Convolution Encoder.

    PG026 rule: each of the two codes is ``input_rate`` (n) bits long and the
    combined number of 1-bits across both equals ``output_rate`` (m), with
    n < m < 2n. We pick m of the 2n bit positions uniformly at random; positions
    [0, n) form code0 and [n, 2n) form code1. The exact bit order is irrelevant
    to validity (only length and total popcount matter), so any such pattern is
    legal. Returns the two codes as zero-padded n-bit binary strings (puncture
    codes have no radix parameter, so they are entered as bit strings).
    """
    positions = random.sample(range(2 * input_rate), output_rate)
    code0 = code1 = 0
    for p in positions:
        if p < input_rate:
            code0 |= 1 << p
        else:
            code1 |= 1 << (p - input_rate)
    fmt = "0{}b".format(input_rate)
    return format(code0, fmt), format(code1, fmt)


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


def max_subset_sum_by_key(
    items: Iterable[Any],
    target: int,
    key: Callable[[Any], int],
) -> Optional[List[Any]]:
    """
    Return a maximal-cardinality subset of `items` whose key-summed value equals `target`.

    This is the counterpart to `min_subset_sum_by_key`: same exact-sum constraint,
    but it returns the subset using the *most* elements rather than the fewest.
    It is used when balancing an AXI Stream source surplus, where the goal is to
    pack as many sources as possible into a single (width-matched) sink.

    Each item is unique by index. Only non-negative integer key values are supported.

    Returns
    -------
    list[Any] | None
        A list of objects that sum to `target` with the most elements, or None if
        impossible. Returns [] when target == 0.

    Complexity
    ----------
    Time  : O(n * target)
    Space : O(target)
    """

    objs = list(items)
    vals = []
    for o in objs:
        v = key(o)
        if not isinstance(v, int) or v < 0:
            raise ValueError("key(obj) must return a non-negative integer.")
        vals.append(v)

    # dp[s] = maximal count of items to reach sum s (-1 = unreachable)
    dp = [-1] * (target + 1)
    prev = [None] * (target + 1)
    dp[0] = 0

    # 0-1 knapsack transition, sums iterated downward to avoid reusing an item.
    for i, a in enumerate(vals):
        if a == 0 or a > target:
            continue
        for s in range(target - a, -1, -1):
            if dp[s] != -1 and dp[s] + 1 > dp[s + a]:
                dp[s + a] = dp[s] + 1
                prev[s + a] = (s, i)

    if dp[target] == -1:
        return None

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
    # Choose each representative and order the result deterministically. `comp`
    # is a set of node objects, so `next(iter(comp))` would pick an id-ordered
    # (run-to-run nondeterministic) element; key on a stable attribute instead so
    # generation is reproducible for a fixed --seed.
    def _key(node):
        return getattr(node, "hier_name", str(node))

    reps = [
        min(comp, key=_key) for i, comp in enumerate(sccs) if outdeg[i] == 0
    ]
    reps.sort(key=_key)

    return reps
