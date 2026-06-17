# RandSoC (Random SoC Design Generator)

This project is a Python-based tool for generating random System on Chip (SoC) designs. Currently it only supports creating designs in the Xilinx Vivado toolchain.  The tool creates a random design by:
1. Randomly selecting a set of Xilinx IP blocks from a list of supported IP (support for each IP must be manually added.  Currently several IP blocks are supported, but more can be added in a fairly straightforward manner).
1. Randomizing the configurations of the selected IP blocks.
1. Instantiating the selected IP blocks in a top-level design.
1. Connecting the instantiated IP blocks together using a random interconnect topology.
1. Generating a Tcl script that can be used to create the design in Vivado.

The tool can be used to generate large datasets of random hardware designs for use in machine learning, CAD research, and other applications.

## Dependencies

The tool has been tested on Python 3.12.3 and Ubuntu 24.04, but it should be fairly easy to run on other Python 3.x versions and Linux distributions (assuming they support Vivado).

Python dependencies are listed in the `requirements.txt` file.  It is recommended to create a virtual environment and install the dependencies there.  To do this, run:

```bash
make env
```

The virtual environment will be created in the `.venv` directory.  To activate the virtual environment, run:

```bash
source .venv/bin/activate
```

## Quickstart

```bash
make env                                       # one-time: create .venv, install deps
make run CONFIG=configs/default.yaml SEED=0     # generate ./temp/design.tcl
make vivado                                    # build temp/design.tcl in Vivado
```

A design is produced from a YAML config (which IP, how many, Vivado version,
interconnect strategy) plus a random seed; the same config + seed + part is fully
reproducible. The tool randomly selects between `min_ip` and `max_ip` blocks from
the config's `available_ip` (with replacement) and adds whatever infrastructure
IP (clock, interconnect, interrupt controller, stream adapters, …) is needed to
complete connectivity.

The full CLI, the `RandomDesign` Python API, the Makefile targets (`run`,
`run-bd`, `vivado`, `smoke`, `vivado-test`, …), and the configuration-file
reference live in the documentation below.

## Documentation

- [Documentation index](docs/index.md) — tool overview, how to run (CLI, Python,
  Makefile targets), and an architecture walkthrough.
- [Configuration File Reference](docs/config.md) — every key the config YAML
  accepts (IP selection, Vivado version, AXI no-master strategy, AXIS converters).
- [AXI4-Stream Connection](docs/axi_stream.md) — how RandSoC wires up AXI-Stream
  IP, including the source/sink assignment algorithm and width converters.
- [Adding and Defining IP](docs/ip.md) — the IP YAML schema, how to add a new IP
  block, and the **complete [Supported IP](docs/ip.md#supported-ip) list**
  (randomized IP plus the IP added as needed).

## Supported IP

RandSoC supports a range of randomly-configured Xilinx IP (GPIO, UART, FFT,
CORDIC, Convolution Encoder, MicroBlaze, the AXI DMA family, …) plus the
infrastructure IP added as a design requires it (interconnect, clocking,
interrupt controller, and the AXI-Stream helpers). The full, canonical tables —
with per-IP descriptions, links, and supported-configuration notes — live in
[Adding and Defining IP → Supported IP](docs/ip.md#supported-ip).

## Adding new IP

New IP is defined by a small Python class plus a YAML file describing the inner
Xilinx IP, its randomizable parameters, and ports. See
[Adding and Defining IP](docs/ip.md) for the full schema and a worked example.