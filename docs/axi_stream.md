# AXI4-Stream Connection

This document describes how RandSoC wires up **AXI4-Stream** IP. Unlike the
memory-mapped AXI and scalar wire connectors, AXI-Stream is a point-to-point,
directional protocol: a *master/source* port drives a *slave/sink* port. This
requires a dedicated connection strategy, implemented primarily in
[`port_assigner.py`](../rand_soc/port_assigner.py).

## Overview

The relevant pieces of the implementation are:

- **[`port_assigner.py`](../rand_soc/port_assigner.py)** — `port_assigner_axis()`,
  the graph algorithm that decides *which source drives which sink*.
- **[`utils.py`](../rand_soc/utils.py)** — two supporting helpers:
  `min_subset_sum_by_key()` (subset-sum DP) and `sink_scc_representatives()`
  (strongly-connected-component analysis).
- **[`ip/axis_broadcaster.py`](../rand_soc/ip/axis_broadcaster.py)** — wraps the
  Xilinx `axis_broadcaster` IP to fan one source out to multiple sinks.
- **[`ip/fft.py`](../rand_soc/ip/fft.py)** / [`ip/fft.yaml`](../rand_soc/ip/fft.yaml) —
  a multi-port stream IP used to exercise the flow.
- **[`typedefs.py`](../rand_soc/typedefs.py)** — adds the `AXI_STREAM` protocol and
  the `INTERFACE` net type (vs. plain `WIRE`), since stream ports are bundled
  interfaces, not scalar wires.
- IP base helpers in [`ip/ip_base.py`](../rand_soc/ip/ip_base.py):
  `has_axis_ports()`, `get_axis_master_ports()`, `get_axis_slave_ports()`, etc.

## Concepts

Every AXIS port-bearing IP is classified into one of three roles
([`creator.py`](../rand_soc/creator.py), `_axi_stream()`):

- **Primary sources** — IP with only master ports (pure producers). If none
  exist, 8 external source ports are synthesized.
- **Primary sinks** — IP with only slave ports (pure consumers). If none exist,
  one external sink is synthesized.
- **Internal IP** — everything with both master and slave ports (e.g. FFT,
  broadcaster) that sits in the middle of the dataflow.

`port_assigner_axis()` returns a `{sink_port: [source_ports]}` map; the
`_axi_stream_connector()` method then realizes it in the block design.

## The connection algorithm (`port_assigner_axis`)

The algorithm runs in **four phases**, each maintaining `unconnected_sources`,
`unconnected_sinks`, and `unconnected_ip` sets.

### Phase 1 — Splice every internal IP into the network

Greedily pull internal IP in one at a time. For each, find an unconnected source
whose width *matches* one of the IP's slave ports; if a match exists, connect it,
otherwise pick a random source (a width converter is implied for later).
Crucially, once an IP is connected, **its master ports become new available
sources**.

Doing this sequentially (rather than all at once) is deliberate: it prevents
"floating islands" of IP that only form circular connections among themselves
with no path back to a primary source.

### Phase 2 — Guarantee every IP can reach a sink

After Phase 1 every IP is *reachable from* a source, but some may have no path
*to* a primary sink (e.g. an IP feeding a cycle). This is solved with
**strongly-connected-component (SCC) analysis**:

- Build a directed graph of IP→IP stream edges.
- `sink_scc_representatives()` condenses the graph into its SCC DAG and returns
  one representative node from each **sink SCC** (components with no outgoing
  edges).

The theorem it exploits: if you add an edge from each sink-SCC representative to
a new terminal node `t`, *every* node in the graph can reach `t`. So those
representatives are exactly the minimal set of IP that must be wired to a primary
sink to guarantee global drain-ability. Each gets connected to a primary sink,
width-matched where possible.

### Phase 3 — Balance leftover source/sink counts

The remaining loose ends must be made equal in count:

- **More sources than sinks** → some sinks must absorb multiple sources. It uses
  `min_subset_sum_by_key()` — a 0/1-knapsack DP (`O(n·target)`) — to find the
  *fewest* sources whose widths sum exactly to the sink's width ("perfectly
  driving"). At realization time this becomes an **AXI-Stream Combiner**. Falls
  back to a random multi-source pick if no perfect subset exists.
- **More sinks than sources** → sources must be reused, again using subset-sum to
  perfectly drive sinks from already-connected sources; this becomes an
  **AXI-Stream Broadcaster**.

### Phase 4 — Pair the remainder one-to-one

With equal counts, remaining sinks are popped and matched to a width-equal source
if possible, else randomly (width converter implied). The algorithm asserts that
all sources and sinks have been consumed.

## Realization (`_axi_stream_connector`)

The `_axi_stream_connector()` method turns the abstract assignment map into
hardware:

1. Count fanout per driver source.
2. Any source feeding more than one sink gets an `AxisBroadcaster` instance
   (Xilinx `axis_broadcaster` with `NUM_MI = degree`); each consumer connects to
   a distinct `M_AXIS_n` output.
3. Single-fanout connections wire source directly to sink.

## Status and known limitations

The AXI-Stream support is still under active development. Current gaps:

- **Width converters** and the **AXI-Stream Combiner** referenced throughout the
  algorithm are *planned but not yet implemented*. The assigner records width
  mismatches and multi-source-to-one-sink intent, but `_axi_stream_connector()`
  currently only handles broadcasters and asserts `len(drivers) == 1`. A combiner
  assignment would trip that assertion.
