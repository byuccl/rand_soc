from collections import defaultdict
import logging
import random
from typing import List
import networkx as nx
from ordered_set import OrderedSet

from .ports import IpPort, Port
from .ip.ip_base import IP
from .utils import (
    max_subset_sum_by_key,
    min_subset_sum_by_key,
    sink_scc_representatives,
)


def port_assigner_random(in_ports, out_ports):
    """Randomly make connection assignments from out_ports to in_ports, such that each in_port is fully driven.
    This does not actually make the connections, it just returns the assignments.

    Returns: a dictionary mapping each in_port to a list of (out_port, high_bit, low_bit) tuples.

    """

    drivers_for_port = defaultdict(list)

    if not in_ports and not out_ports:
        return drivers_for_port

    logging.info(
        f"Will randomly connect {len(out_ports)} output ports to {len(in_ports)} input ports"
    )

    # Generate list of in and out ports, where each item is a tuple (port, index)
    # where index is the lowest bit number not connected
    in_ports_not_driven = [[port, 0] for port in in_ports]
    random.shuffle(in_ports_not_driven)

    out_ports_unused = [[port, 0] for port in out_ports]
    assert out_ports_unused

    # Connect all in ports
    next_out_port_idx = 0

    for in_port_and_pin_idx in in_ports_not_driven:
        drivers = []
        in_port = in_port_and_pin_idx[0]
        in_width = in_port.width
        in_width_unconnected = in_width
        logging.info(f"Connecting drivers of port {in_port.hier_name} [{in_width-1}:0]")

        num_connected = 0

        while in_width_unconnected:
            # Once we've used up all the output signals, this flag will switch to True
            # and we will randomly reuse output signals
            using_random_output = next_out_port_idx >= len(out_ports_unused)

            # Pick the output port
            if using_random_output:
                out_port = random.choice(out_ports_unused)[0]
                out_port_avail = None
                # Randomly pick a pin range to use
                out_width = min(out_port.width, in_width_unconnected)
                out_bit_low = random.randint(0, out_port.width - out_width)
                out_bit_high = out_bit_low + out_width - 1
            else:
                out_port = out_ports_unused[next_out_port_idx][0]
                # Identify unused pins from this port
                out_port_avail = out_ports_unused[next_out_port_idx]
                out_bit_high = out_port_avail[0].width - 1
                out_bit_low = out_port_avail[1]

            out_width = out_bit_high - out_bit_low + 1

            if out_width == in_width_unconnected:
                logging.info(
                    f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
                )
                drivers.append((out_port, out_bit_high, out_bit_low))
                num_connected += out_width
                next_out_port_idx += 1
                in_width_unconnected = 0
                break

            if out_width > in_width_unconnected:
                logging.info(
                    f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_low + in_width_unconnected - 1}:{out_bit_low}]"
                )
                drivers.append(
                    (out_port, out_bit_low + in_width_unconnected - 1, out_bit_low)
                )
                num_connected += in_width_unconnected
                if out_port_avail:
                    out_port_avail[1] += in_width_unconnected
                in_width_unconnected = 0
                break

            # out_width < in_width_unconnected
            logging.info(
                f"  [{in_width_unconnected-1}:{in_width_unconnected-out_width}] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
            )
            drivers.append((out_port, out_bit_high, out_bit_low))
            num_connected += out_width
            next_out_port_idx += 1
            in_width_unconnected -= out_width

        assert (
            num_connected == in_width
        ), f"num_connected: {num_connected}, in_width: {in_width}"

        drivers_for_port[in_port] = drivers

    return drivers_for_port


def _same_ip(source, sink):
    """True if a source and sink belong to the same IP (i.e. a self-loop)."""
    return (
        isinstance(source, IpPort)
        and isinstance(sink, IpPort)
        and source.ip is sink.ip
    )


def port_assigner_axis(
    primary_sources: List[Port],
    primary_sinks: List[Port],
    internal_ip: List[IP],
):
    """Make connections from sources to sinks for AXI Stream ports. This does not actually make the connections,
    it just returns the assignments.
    Returns: a dictionary mapping each sink port to a list of source ports.
    """
    assert isinstance(primary_sources, list)
    assert isinstance(primary_sinks, list)
    assert isinstance(internal_ip, list)

    connections = defaultdict(list)

    # OrderedSet (not a plain set): the assigner makes random.choice / first-match
    # decisions while iterating these collections, and a plain set of port/IP
    # objects iterates in id() (memory-address) order, which varies run to run
    # regardless of PYTHONHASHSEED -- making generation nondeterministic for a
    # fixed --seed. Insertion order (derived from the seeded construction) is
    # stable.
    all_sources = OrderedSet(primary_sources)
    unconnected_sources = OrderedSet(primary_sources)
    unconnected_ip = OrderedSet(internal_ip)
    unconnected_sinks = OrderedSet(primary_sinks)

    # Loop through the internal IP, and connect them to the AXI stream network
    # one by one, until no unconnected IP remain.  This is done in sequence to
    # avoid floating islands of IP that only have circular connections between themselves.
    logging.info("AXI Stream Phase 1: Connect internal IP to AXI Stream network")
    while unconnected_ip:

        # 1. Find a new IP to connect to the AXI stream network
        # - Look for an IP that has an AXI stream sink ports matching the
        #   width of one of the unconnected sources.
        candidate_source_port = None
        candidate_sink_port = None
        ip_to_connect = None
        for ip in unconnected_ip:
            for sink_port in ip.get_axis_slave_ports():
                matches = [
                    port
                    for port in unconnected_sources
                    if port.width == sink_port.width
                ]
                if matches:
                    candidate_source_port = random.choice(matches)
                    candidate_sink_port = sink_port
                    ip_to_connect = ip
                    break
            if candidate_source_port:
                logging.info(
                    f"+ Matching width found to drive {candidate_sink_port.hier_name_w} by {candidate_source_port.hier_name_w}"
                )
                break

        # 2. If no candidate found, then just randomly pick a source port,
        # and a width converter will be added later to connect it.
        if candidate_source_port is None:
            candidate_source_port = random.choice(list(unconnected_sources))
            ip_to_connect = random.choice(list(unconnected_ip))
            candidate_sink_port = random.choice(ip_to_connect.get_axis_slave_ports())
            logging.info(
                f"- No matching width found, randomly driving {candidate_sink_port.hier_name_w} by {candidate_source_port.hier_name_w}"
            )

        # 3. Save the connection from the candidate source port to the IP sink port
        unconnected_ip.remove(ip_to_connect)
        connections[candidate_sink_port].append(candidate_source_port)
        unconnected_sources.remove(candidate_source_port)

        # 4. Add the IP's other AXI stream ports to the unconnected sources/sinks
        unconnected_sources.update(ip_to_connect.get_axis_master_ports())
        all_sources.update(ip_to_connect.get_axis_master_ports())
        unconnected_sinks.update(
            [
                port
                for port in ip_to_connect.get_axis_slave_ports()
                if port != candidate_sink_port
            ]
        )

    # At this point all internal IP should be reachable from the AXI stream
    # primary sources. We now need to make sure nodes can reach one of the primary sinks.
    logging.info("AXI Stream Phase 2: Ensure all internal IP can reach primary sinks")

    # Build a directed graph of IP to IP AXI stream connections, and use it to find
    # a minimal set of IP that need to drive sinks to ensure all IP can reach a sink.
    G = nx.DiGraph()
    # Include every internal IP as a node -- an IP connected only via an external
    # source adds no IP->IP edge, but its master still must reach a sink. Without
    # this it would be missed here and later forced to drive its own slave.
    G.add_nodes_from(internal_ip)
    for sink_port, source_ports in connections.items():
        for source_port in source_ports:
            if isinstance(source_port, IpPort):
                G.add_edge(source_port.ip, sink_port.ip)
    ip_to_drive_sinks = sink_scc_representatives(G)
    logging.info(
        f"- {len(ip_to_drive_sinks)} IP need to drive sinks to ensure connectivity"
    )

    # Loop through all the IP that need to drive sinks, and connect them to primary sinks
    for source_ip in ip_to_drive_sinks:

        # Find an AXI stream master port from this IP that is unconnected
        # and matches the width of a primary sink that is unconnected
        candidate_source_port = None
        candidate_sink_port = None
        for source_port in source_ip.get_axis_master_ports():
            if source_port not in unconnected_sources:
                continue
            matches = [
                port
                for port in primary_sinks
                if port not in connections and port.width == source_port.width
            ]
            if matches:
                candidate_source_port = source_port
                candidate_sink_port = random.choice(matches)
                break

        if candidate_sink_port is None:
            possible_sinks = [
                port for port in primary_sinks if port not in unconnected_sinks
            ]
            if possible_sinks:
                candidate_sink_port = random.choice(possible_sinks)
        if candidate_source_port is None:
            # No unconnected sink ports available, pick any sink port
            candidate_sink_port = random.choice(primary_sinks)

        if candidate_source_port is None:
            # Pick a random unconnected source port from this IP
            possible_sources = [
                port
                for port in source_ip.get_axis_master_ports()
                if port in unconnected_sources
            ]
            if possible_sources:
                candidate_source_port = random.choice(possible_sources)
        if candidate_source_port is None:
            # No unconnected source ports available, pick any source port
            candidate_source_port = random.choice(source_ip.get_axis_master_ports())

        assert candidate_source_port is not None
        assert candidate_sink_port is not None

        if candidate_source_port.width == candidate_sink_port.width:
            logging.info(
                f"+ Matching width found to drive {candidate_sink_port.hier_name_w} by {candidate_source_port.hier_name_w}"
            )
        else:
            logging.info(
                f"- No matching width found, driving {candidate_sink_port.hier_name_w} by {candidate_source_port.hier_name_w}"
            )
        connections[candidate_sink_port].append(candidate_source_port)
        if candidate_source_port in unconnected_sources:
            unconnected_sources.remove(candidate_source_port)
        if candidate_sink_port in unconnected_sinks:
            unconnected_sinks.remove(candidate_sink_port)

    # There may still be unconnected sources and sinks.
    # The primary_sinks will need to be connected to the network as well, and at this
    # point, we can add the primary_sinks to the unconnected_sinks list, since all
    # internal IP are now connected.

    # The next phase will perform connections until equal number of sources and sinks remain.
    #
    # This means that if we have more sinks than sources, we will be reusing sources, and
    # at connection time, an AXI Stream Broadcaster will be added to drive multiple sinks from a single source.
    #
    # If we have more sources than sinks, we will be reusing sinks, and
    # at connection time, an AXI Stream Combiner will be added to combine multiple sources into a single sink.
    logging.info(
        f"AXI Stream Phase 3: Balance sources ({len(unconnected_sources)}) and sinks ({len(unconnected_sinks)})"
    )

    # First, handle the case where we have more sources than sinks. We shrink the
    # surplus by driving a single sink with *multiple* sources (an AXI Stream
    # Combiner at connection time). Each such combine reduces the surplus by
    # (group_size - 1), so to make progress we want to pack as MANY surplus
    # sources into a sink as possible -- the largest width-matched group, not the
    # smallest. The group is drawn from unconnected sources only; reusing an
    # already-connected source would not reduce the surplus.
    while len(unconnected_sources) > len(unconnected_sinks) and unconnected_sinks:
        surplus = len(unconnected_sources) - len(unconnected_sinks)

        # Prefer the sink we can drive with the largest width-matched group,
        # without consuming so many sources that we overshoot below balance.
        # Candidate sources for a sink never include sources on its own IP.
        best_sink = None
        best_group = None
        for sink in unconnected_sinks:
            pool = [s for s in unconnected_sources if not _same_ip(s, sink)]
            group = max_subset_sum_by_key(pool, sink.width, key=lambda p: p.width)
            if not group or len(group) < 2:
                continue
            if len(group) - 1 > surplus:
                continue
            if best_group is None or len(group) > len(best_group):
                best_sink, best_group = sink, group

        if best_group is not None:
            sink, group = best_sink, best_group
            logging.info(
                f"+ Width-matched combine of {sink.hier_name_w} from "
                f"{', '.join(s.hier_name_w for s in group)}"
            )
        else:
            # No clean width-matched group available; force a combine from this
            # sink's cross-IP sources and let a width converter absorb the
            # mismatch. Consume enough sources to make progress without
            # overshooting balance.
            sink = random.choice(
                [
                    k
                    for k in unconnected_sinks
                    if any(not _same_ip(s, k) for s in unconnected_sources)
                ]
                or list(unconnected_sinks)
            )
            pool = [s for s in unconnected_sources if not _same_ip(s, sink)]
            num_sources = min(surplus + 1, len(pool))
            group = random.sample(pool, max(num_sources, 1)) if pool else []
            logging.info(
                f"- Width-mismatched combine of {sink.hier_name_w} from "
                f"{', '.join(s.hier_name_w for s in group)}"
            )

        connections[sink] = group
        unconnected_sinks.remove(sink)
        for s in group:
            unconnected_sources.remove(s)

    # Symmetric to the sinks>sources case below (which reuses already-connected
    # sources as broadcasters): if a net source surplus remains but every sink is
    # already connected, reuse an already-connected, cross-IP sink, turning it
    # into a combiner. Without this a source-heavy design (e.g. several read-only
    # DMAs) strands a source and fails the Phase 4 balance assertion.
    while unconnected_sources and not unconnected_sinks:
        source = unconnected_sources.pop()
        connected_sinks = [s for s in connections if not _same_ip(source, s)]
        sink = random.choice(connected_sinks or list(connections))
        connections[sink].append(source)
        logging.info(
            f"+ Combining surplus source {source.hier_name_w} into "
            f"already-connected sink {sink.hier_name_w}"
        )

    # Next, handle the case where we have more sinks than sources. Extra sinks are
    # driven by reusing an already-connected source (a broadcaster), never a
    # source on the sink's own IP.
    while len(unconnected_sinks) > len(unconnected_sources):
        connected_sources = list(all_sources - unconnected_sources)

        chosen_sink = None
        candidate_sources = None
        for sink in unconnected_sinks:
            pool = [s for s in connected_sources if not _same_ip(s, sink)]
            candidate_sources = min_subset_sum_by_key(
                pool, sink.width, key=lambda x: x.width
            )
            if candidate_sources:
                chosen_sink = sink
                logging.info(
                    f"+ Perfectly driving {sink.hier_name_w} by {', '.join([s.hier_name_w for s in candidate_sources])}"
                )
                break

        if candidate_sources is None:
            # No clean width-matched reuse; drive a sink from one of its cross-IP
            # sources and add a width converter later. Prefer an already-connected
            # source (a true broadcaster); fall back to any cross-IP source (it is
            # still paired in Phase 4, so it just drives an extra sink) so a
            # sink-heavy design with no source connected yet never strands a sink.
            chosen_sink = random.choice(list(unconnected_sinks))
            pool = [s for s in connected_sources if not _same_ip(s, chosen_sink)]
            cross_ip_any = [s for s in all_sources if not _same_ip(s, chosen_sink)]
            candidate_sources = [random.choice(pool or cross_ip_any or connected_sources or list(all_sources))]
            logging.info(
                f"- No perfect multi-source sink found, randomly driving {chosen_sink.hier_name_w} by {', '.join([s.hier_name_w for s in candidate_sources])}"
            )

        connections[chosen_sink] = candidate_sources
        unconnected_sinks.remove(chosen_sink)

    # At this point, the number of unconnected sources and sinks should be equal, try and connect them
    # one-by-one, matching widths where possible, otherwise randomly.
    logging.info(
        f"AXI Stream Phase 4: Final connections of remaining {len(unconnected_sources)} sources and {len(unconnected_sinks)} sinks"
    )
    assert len(unconnected_sinks) == len(
        unconnected_sources
    ), f"Unconnected sources ({len(unconnected_sources)}) and sinks ({len(unconnected_sinks)}) should be equal"
    while unconnected_sinks:
        sink = unconnected_sinks.pop()
        # Never drive a sink from a source on its own IP (no self-loops). Phase 2
        # routes every IP's master to a sink, so a cross-IP source should always
        # remain here; fall back (with a warning) only if that ever fails.
        candidates = [s for s in unconnected_sources if not _same_ip(s, sink)]
        if not candidates:
            logging.warning(f"  no cross-IP source available for {sink.hier_name_w}")
            candidates = list(unconnected_sources)
        matches = [s for s in candidates if s.width == sink.width]
        if matches:
            source = random.choice(matches)
            logging.info(
                f"+ Matching width found to drive {sink.hier_name_w} by {source.hier_name_w}"
            )
        else:
            source = random.choice(candidates)
            logging.info(
                f"- No matching width found, randomly driving {sink.hier_name_w} by {source.hier_name_w}"
            )
        connections[sink].append(source)
        unconnected_sources.remove(source)

    assert not unconnected_sources
    assert not unconnected_sinks

    return connections


# def port_assigner_axis(in_ports, out_ports):
#     """Make connection assignments from out_ports to in_ports, such that each in_port is fully driven.
#     This does not actually make the connections, it just returns the assignments.

#     Returns: a dictionary mapping each in_port to a list of ports from out_ports.

#     """

#     drivers_for_port = defaultdict(list)

#     unassigned_in_ports = list(in_ports)
#     random.shuffle(unassigned_in_ports)

#     unassigned_out_ports = list(out_ports)

#     # Loop through all in_ports, and look for an out_port with the same width,
#     # or a combination of out_ports that can be concatenated to match the width.
#     #
#     # First pass:
#     # - don't allow reuse of output ports.
#     # - ignore in_ports where no exact match width match is possible
#     for in_port in unassigned_in_ports:
#         unassigned_out_ports_diff_ip = [
#             p for p in unassigned_out_ports if p.ip != in_port.ip
#         ]
#         matched_ports = min_subset_sum_by_key(
#             unassigned_out_ports_diff_ip, in_port.width, key=lambda x: x.width
#         )
#         if matched_ports is None:
#             continue
#         drivers_for_port[in_port] = matched_ports
#         unassigned_in_ports.remove(in_port)
#         for p in matched_ports:
#             unassigned_out_ports.remove(p)

#     # Second pass:
#     # - allow reuse of output ports
#     for in_port in unassigned_in_ports:
#         out_ports_diff_ip = [p for p in out_ports if p.ip != in_port.ip]
#         matched_ports = min_subset_sum_by_key(
#             out_ports_diff_ip, in_port.width, key=lambda x: x.width
#         )
#         if matched_ports is None:
#             continue
#         drivers_for_port[in_port] = matched_ports
#         unassigned_in_ports.remove(in_port)
#         for p in matched_ports:
#             if p in unassigned_out_ports:
#                 unassigned_out_ports.remove(p)

#     if not unassigned_in_ports:
#         return drivers_for_port

#     print(len(unassigned_in_ports), "in ports remain unassigned")
#     print(len(unassigned_out_ports), "out ports remain unassigned")

#     # Third pass:
#     # - Assign remaining unassigned out ports to remaining unassigned in ports, in round-robin fashion
#     max_idx = max(len(unassigned_in_ports), len(unassigned_out_ports))
#     for idx in range(max_idx):
#         drivers_for_port[unassigned_in_ports[idx % len(unassigned_in_ports)]] += [
#             unassigned_out_ports[idx % len(unassigned_out_ports)]
#         ]

#     return drivers_for_port
