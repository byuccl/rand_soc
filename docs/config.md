# Configuration File Reference

RandSoC's randomization is driven by a YAML configuration file, passed as the
second positional argument to [`main.py`](../main.py) (or via `CONFIG=` to the
[`Makefile`](../Makefile)). This page documents every key the config accepts.

Two example configs ship with the repo: [`configs/default.yaml`](../configs/default.yaml)
(a broad peripheral mix) and [`fft_config.yaml`](../fft_config.yaml) (an
AXI-Stream / FFT focused set).

The config is parsed in [`RandomDesign.create()`](../rand_soc/creator.py). All
keys except `available_ip`, `min_ip`, and `max_ip` are optional and have
back-compatible defaults.

## Top-level keys

### `available_ip` (required)
A list of the IP blocks the generator may pick from. Each entry is a mapping:

- `class` (required) — the Python class name of the IP, matching a class under
  [`rand_soc/ip/`](../rand_soc/ip/) (e.g. `Gpio`, `Microblaze`, `Fft`).
- `max` (optional) — the maximum number of instances of this IP allowed in one
  design. Omit for unlimited.

```yaml
available_ip:
  - class: Microblaze
  - class: Uartlite
  - class: AxiHwicap
    max: 1
```

IP are selected **with replacement** between `min_ip` and `max_ip`, so the same
class may appear multiple times (subject to `max`). Additional infrastructure IP
(clock generator, AXI interconnect, interrupt controller, AXIS broadcaster /
combiner / width converter, etc.) is added automatically to complete
connectivity and is **not** counted against `max_ip`.

### `min_ip` / `max_ip` (required)
Integers bounding the number of IP randomly drawn from `available_ip`. The count
is `random.randint(min_ip, max_ip)`.

### `vivado_version` (optional, default `v2022_2`)
The Vivado version the design targets, one of `v2020_2`, `v2022_2`, `v2024_2`.
This drives two things:

1. **IP version resolution.** IP modules are loaded from
   [`rand_soc/ip/<version>/`](../rand_soc/ip/) with fallback to older versions
   (`v2024_2` → `v2022_2` → `v2020_2`); see [`import_ip()`](../rand_soc/creator.py).
   This lets version-specific IP variants (e.g. a different `axi_quad_spi`)
   override the base while everything else falls through.
2. **A version guard** in the generated Tcl. The design records its target
   version and errors out if run under a different Vivado, since IP VLNVs are
   version-specific (`v2024_2` → the Tcl checks for `2024.2`).

### `axi_types` (optional, default `[AxiSmartconnect]`)
A list of AXI interconnect classes to choose from: `AxiSmartconnect` and/or
`AxiInterconnect`. One is selected at random for the **entire** design.

```yaml
axi_types: [AxiSmartconnect, AxiInterconnect]
```

## AXI memory-mapped: `axi_mm`

Controls how the memory-mapped AXI network is built.

### `axi_mm.no_master` (optional, default `[external]`)
When a design contains no internal AXI master (e.g. no MicroBlaze), one must be
fabricated to drive the AXI slaves. This key lists the strategies to choose from;
**one is picked at random per design**:

- `external` — bring a top-level AXI master port out to the package pins (legacy
  behavior). A full AXI bus is ~120–130 pins, which can overflow the part's I/O
  budget on pin-limited packages.
- `jtag` — instance a **JTAG-to-AXI master** ([`JtagAxi`](../rand_soc/ip/v2020_2/jtag_axi.py)),
  a real master driven over the device JTAG/BSCAN chain. It consumes **no**
  package pins, avoiding I/O overflow, and is a realistic bring-up master.

```yaml
axi_mm:
  no_master: [external, jtag]   # each design randomly picks one
```

A single-item list forces that strategy (`[jtag]` → always JTAG). Omitting the
key keeps the default external-only behavior.

> Note: the `jtag` strategy requires the `JtagAxi` IP, which currently lives in
> the `v2020_2` IP set (and is reached by version fallback from newer versions).

## AXI-Stream: `axi_stream`

Controls insertion of AXI-Stream data **width converters**
([`AxisDwidthConverter`](../rand_soc/ip/v2020_2/axis_dwidth_converter.py)), which
bridge TDATA width mismatches between a stream source and sink. Without a
converter, Vivado silently zero-pads / truncates the stream (a `BD 41-237`
critical warning), which is functionally wrong. See
[AXI4-Stream Connection](axi_stream.md) for the full stream-wiring story.

Both knobs accept `yes`, `no`, or `random` (default `random`). `yes` inserts a
converter wherever the source and sink widths differ; `no` never does (direct
connect); `random` decides per connection with a coin flip. Matching widths never
get a converter regardless of the setting.

> YAML parses bare `yes`/`no` as booleans; RandSoC normalizes those back to the
> string policies, so you can write them unquoted.

### `axi_stream.io_converters` (optional, default `random`)
Governs connections where one endpoint is an **external** AXIS port (the design's
8-bit external stream source/sink). Because the external interface is 8-bit, a
converter is essentially always feasible here.

### `axi_stream.internal_converters` (optional, default `random`)
Governs **internal** IP-to-IP stream connections.

```yaml
axi_stream:
  io_converters: random
  internal_converters: yes
```

> **Feasibility constraint.** The Xilinx converter is a byte gearbox and requires
> the two TDATA byte widths to have an integer ratio. When an internal pair does
> not (e.g. 5 bytes ↔ 12 bytes), no converter is inserted and the ports are
> connected directly (leaving the width-mismatch warning). The I/O case always
> satisfies the ratio because the external side is one byte.

## Complete example

```yaml
vivado_version: v2024_2

axi_types: [AxiSmartconnect, AxiInterconnect]

axi_mm:
  no_master: [external, jtag]

axi_stream:
  io_converters: random
  internal_converters: random

available_ip:
  - class: Fft
  - class: Microblaze
  - class: Uartlite
    max: 4

min_ip: 3
max_ip: 8
```
