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
- **[`ip/v2020_2/axis_broadcaster.py`](../rand_soc/ip/v2020_2/axis_broadcaster.py)** /
  **[`ip/v2020_2/axis_combiner.py`](../rand_soc/ip/v2020_2/axis_combiner.py)** — wrap the
  Xilinx `axis_broadcaster`/`axis_combiner` IP to fan one source out to multiple
  sinks (1→N) and merge multiple sources into one sink (N→1).
- **[`ip/v2020_2/fft.py`](../rand_soc/ip/v2020_2/fft.py)** / [`ip/v2020_2/fft.yaml`](../rand_soc/ip/v2020_2/fft.yaml) —
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
  exist, a single 8-bit external source port is synthesized; the assigner
  broadcasts it when more than one sink needs driving.
- **Primary sinks** — IP with only slave ports (pure consumers). If none exist,
  one 8-bit external sink is synthesized.
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

- Build a directed graph that includes **every** internal IP as a node
  (`G.add_nodes_from(internal_ip)`) plus the IP→IP stream edges. Adding the nodes
  explicitly matters: an IP driven only by an external source has no incoming
  IP→IP edge, and without being a node its master would never be routed to a sink
  — it would later be forced onto its own slave (a self-loop).
- `sink_scc_representatives()` condenses the graph into its SCC DAG and returns
  one representative node from each **sink SCC** (components with no outgoing
  edges).

The theorem it exploits: if you add an edge from each sink-SCC representative to
a new terminal node `t`, *every* node in the graph can reach `t`. So those
representatives are exactly the minimal set of IP that must be wired to a primary
sink to guarantee global drain-ability. Each gets connected to a primary sink,
width-matched where possible.

**No IP drives itself.** Throughout Phases 3 and 4, source selection is filtered
to *cross-IP* candidates (`_same_ip(source, sink)` is excluded), so an IP's master
is never wired to one of its own slaves. Combined with the Phase 2 node fix, this
enforces the no-self-loop invariant *during* connection creation rather than via a
post-pass repair.

### Phase 3 — Balance leftover source/sink counts

The remaining loose ends must be made equal in count:

- **More sources than sinks** → some sinks must absorb multiple sources. It uses
  `max_subset_sum_by_key()` — a 0/1-knapsack DP (`O(n·target)`) — to find a set of
  cross-IP sources whose widths sum exactly to the sink's width ("perfectly
  driving"). At realization time this becomes an **AXI-Stream Combiner**. Falls
  back to a random multi-source pick if no perfect subset exists.
- **More sinks than sources** → sources must be reused. `min_subset_sum_by_key()`
  picks already-connected sources to perfectly drive each remaining sink; this
  becomes an **AXI-Stream Broadcaster**.

### Phase 4 — Pair the remainder one-to-one

With equal counts, remaining sinks are popped and matched to a width-equal,
cross-IP source if possible, else a random cross-IP source (a width converter is
inserted at realization if the widths differ). The algorithm asserts that all
sources and sinks have been consumed.

## Realization (`_axi_stream_connector`)

The `_axi_stream_connector()` method turns the abstract `{sink: [sources]}` map
into hardware:

1. **Fanout → broadcaster.** Count how many sinks each driver feeds. A driver
   feeding more than one sink gets an `AxisBroadcaster` (Xilinx `axis_broadcaster`
   with `NUM_MI = degree`); each consumer takes a distinct `M_AXIS_n` output.
2. **Fan-in → combiner.** A sink fed by more than one driver gets an
   `AxisCombiner` (`axis_combiner` with `NUM_SI = degree`); each driver connects to
   a distinct `S_AXIS_n` input, sized to that driver's width.
3. **Single connections** wire the resolved source to the sink.

Every source→sink connection (direct, broadcaster leg, or combiner leg) is made
through `_connect_axis()`, which inserts an **AXI-Stream Data Width Converter**
([`AxisDwidthConverter`](../rand_soc/ip/v2020_2/axis_dwidth_converter.py)) when the
two widths differ and the config asks for one.

## Width converters and configuration

Two config knobs (see [config.md](config.md#axi-stream-axi_stream)) control
converter insertion, each `yes` / `no` / `random` (default `random`):

- `axi_stream.io_converters` — connections touching an external (8-bit) AXIS port.
- `axi_stream.internal_converters` — internal IP-to-IP connections.

Without a converter a width mismatch is left as a direct connection, which Vivado
accepts but flags (`BD 41-237 TDATA_NUM_BYTES does not match`) while silently
zero-padding or truncating the stream. A converter bridges the widths properly.

The Xilinx converter is a byte gearbox and requires the two TDATA **byte** widths
to have an integer ratio. The external-facing (I/O) case is always feasible (the
external side is one byte); for internal pairs whose byte widths are not an
integer multiple, no converter is inserted and the connection is left direct.

## Status and known limitations

- The **broadcaster**, **combiner**, and **width converter** described above are
  all implemented.
- **Combiner output → sink** width mismatches are not yet converted (a combiner
  concatenates its inputs; if that sum differs from the sink width the mismatch
  remains). The converters cover source→sink legs.
- **Non-integer-byte-ratio internal pairs** are left as direct connections (see
  above), since the Xilinx converter cannot bridge them.
