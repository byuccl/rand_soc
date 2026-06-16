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
- [Adding and Defining IP](docs/ip.md) — the IP YAML schema and how to add a new
  IP block.

## Supported IP

### Randomized IP
| Python Class | Description | Supported Configurations |
|---------|-------------|--------------------------|
|`Accumulator` | Xilinx *Accumulator* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/accumulator.html>) | Full configuration space |
|`AxiCan` | Xilinx *AXI CAN* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_can.html>) | Full configuration space, but untested as a separate license is required. |
|`AxiCdma` | Xilinx *AXI AXI Central DMA Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_central_dma.html>) | Full configuration space |
|`AxiDma` | Xilinx *AXI Direct Memory Access* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_dma.html>) | Full configuration space (SG/direct/Micro/multichannel, MM2S+S2MM, control/status streams) |
|`AxiEthernetLite` | Xilinx *AXI Ethernet Lite* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_ethernetlite.html>) | Full configuration space |
|`AxiHwicap` | Xilinx *AXI Hardware ICAP* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_hwicap.html>) | Full configuration space |
|`AxiIic` | Xilinx *AXI IIC Bus Interface* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_iic.html>) | Full configuration space |
|`AxiQuadSpi` | Xilinx *AXI Quad SPI* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_quadspi.html>) | Full configuration space |
|`AxiTimer` | Xilinx *AXI Timer/Counter* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_timer.html>) | Full configuration space |
|`AxiUsb2Device` | Xilinx *AXI USB 2.0 Device Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_usb2_device.html>) | Full configuration space, but untested as a separate license is required. |
|`Dft` | Xilinx *Discrete Fourier Transform (DFT)* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/dft.html>) | Full configuration space |
|`Emc` | Xilinx *AXI External Memory Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_emc.html>) | Only number of banks. Other options not yet enumerated. |
|`Gpio` | Xilinx *AXI General Purpose IO* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_gpio.html>) | Full configuration space |
|`Microblaze` | Xilinx *AMD MicroBlaze™ Processor* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/microblaze.html>) | All configurations with local memory bus (No AXI DDR support) |
|`Uartlite` | Xilinx *AXI UART Lite* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_uartlite.html>) | Full configuration space |
|`XadcWiz` | Xilinx *XADC Wizard* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/xadc-wizard.html>) | Full configuration space |

### IP Added as Needed
| Python Class | Description |
|---------|-------------|
|`AxiSmartconnect` | Xilinx *AXI SmartConnect* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/smartconnect.html>) |
|`AxiInterconnect` | Xilinx *AXI Interconnect* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi-interconnect.html>) |
|`ClkGen` | Xilinx *Clocking Wizard* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/clocking_wizard.html>) |
|`Intc` | Xilinx *AXI Interrupt Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_intc.html>) |

## Adding new IP

New IP is defined by a small Python class plus a YAML file describing the inner
Xilinx IP, its randomizable parameters, and ports. See
[Adding and Defining IP](docs/ip.md) for the full schema and a worked example.