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

## Usage Instructions

RandSoC can be run from the command line using the provided `main.py` script: 

```b
usage: main.py [-h] [--seed SEED] [--part PART] output_dir_path config_path

positional arguments:
  output_dir_path  Output directory path
  config_path      Path of rand_soc creator yaml

options:
  -h, --help       show this help message and exit
  --seed SEED      Random seed
  --part PART      Xilinx part name
```

Alternatively you can run it directly from Python:

```python
from rand_soc.creator import RandomDesign

design = RandomDesign(output_dir_path, config_path, seed, part)

# Create the design internally
design.create()

# Write the design out to the output directory
design.write()
```

### YAML configuration file
The design randomization process is controlled by a YAML configuration file.  A default configuration file is provided as `default_config.yaml`.  This file contains:
```yaml
available_ip:
  - class: Accumulator
  - class: AxiCdma
  - class: AxiHwicap
    max: 1
  - class: AxiTimer
  - class: Dft
  - class: Emc
  - class: Gpio
  - class: Microblaze
  - class: Uartlite
  - class: XadcWiz
    max: 1
  - class: AxiEthernetLite
  - class: AxiIic
  - class: AxiQuadSpi


min_ip: 3
max_ip: 18
```

* `available_ip` is a list of the available IP blocks that can be used in the design.  Each entry in the list is a dictionary with the following keys:
  * `class`: The class name of the IP block.  This should match the class name in the Python code for each IP type.  These python classes are located in the `rand_soc/ip` directory.
  * `max`: The maximum number of instances of this IP block that can be used in the design.  This is optional.
* `min_ip`: The minimum number of IP blocks that will be used in the design.
* `max_ip`: The maximum number of IP blocks that will be used in the design.

When the design is created, the tool will randomly select a number of IP blocks between `min_ip` and `max_ip`, and then randomly select the IP blocks from the `available_ip` list.  The IP blocks are selected with replacement, so it is possible to have multiple instances of the same IP block in the design. 

Additional IP will be added to the project in order to complete the design connectivity.  Currently this includes a clock generator, AXI interconnect, and AXI interrupt controller.  These IP blocks are not included in the initial selection process, so the total number of IP blocks in the design may be greater than `max_ip` after the design is created.

### Running in Vivado
When run, the tool will create a *design.tcl* file in the output directory.  This file can be run in Vivado to create the design, and perform synthesis to generate a netlist.  To do this, run the following command:

```bash
vivado -source design.tcl
```

Alternatively, the provided `Makefile` can be used to run the design in Vivado.  To do this, run the following command:

```bash
make vivado
```

To change the default commands that Vivado runs (i.e. disable synthesis), edit the *run.tcl.mustache* file and remove the lines that you do not want to run.  

## Supported IP

### Randomized IP
| Python Class | Description | Supported Configurations |
|---------|-------------|--------------------------|
|`Accumulator` | Xilinx *Accumulator* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/accumulator.html>) | Full configuration space |
|`AxiCan` | Xilinx *AXI CAN* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_can.html>) | Full configuration space, but untested as a separate license is required. |
|`AxiCdma` | Xilinx *AXI AXI Central DMA Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_central_dma.html>) | Full configuration space |
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
|`Axi` | Xilinx *AXI SmartConnect* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/smartconnect.html>) |
|`ClkGen` | Xilinx *Clocking Wizard* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/clocking_wizard.html>) |
|`Intc` | Xilinx *AXI Interrupt Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_intc.html>) |

## IP Configurations

New IP can be added by adding:
1. A new Python class in the `rand_soc/ip` directory.  Example of the `Gpio` class is provided:
```python
from .ip_base import IPrandom

class Gpio(IPrandom):
    @property
    def name(self):
        return "gpio"

    def randomize(self):
        self.load_data_from_yaml(__file__)
```
1. An associated YAML configuration file in the `rand_soc/ip` directory.  This should be named the same as the Python class, but with a `.yaml` extension.  This should contain a list of IP that should be instantiated as part of this logical IP.  Typically this is only one IP, but it can be multiple.  For example, as part of the `Microblaze` IP, the Xilinx Microblaze IP is instantiated, but also the necessary memory blocks that are required as part of the processor.  Each entry in the YAML file should contain:
* `id`: A unique identifier for the IP block.  Example: `"gpio_0"`
* `definition`: The definition of the IP block.  Example: `"xilinx.com:ip:axi_gpio:2.0"`
* `configuration`: A list of configuration parameters for the IP block.  Each item should have:
    * `name`: The name of the configuration parameter.  Example: `"C_GPIO_WIDTH"`
    * `internal`: A boolean indicating if the parameter is internal to the RandSoC tool, or whether it should be passed to the IP block in Vivado.
    * `values`: A list of possible values for the parameter.  Example: `["I", "O", "IO"]`
    * `values_eval`: An alternative list of possible values for the parameter, but evaluated by the tool, with Python functions, other configuration values, and some helper functions available.  Example: `range(1,33)` and `"[0, all_ones(C_GPIO_WIDTH), randintwidth(C_GPIO_WIDTH)]"`
    * `enable`: An evaluated boolean expression that determines if the parameter should be included in the design.  Example: `"C_IS_DUAL and (direction == 'I')"`
    * `format`: The format of the parameter.  Example: `hex`
* `ports`: A list of ports for the IP block.  This is used to expose ports of the instanced IP to the rest of the design.  Each entry should contain:
    * `name`: The name of the port.  Example: `GPIO2`
    * `protocol`: This can be a Xilinx-defined protocol (e.g. `xilinx.com:interface:gpio_rtl:1.0`), or a RandSoC-defined protocol (`clk`, `reset`, `irq`, `data`, `control`)
    * `direction`: The direction of the port. `I` or `O` for non-interface ports, `Master` or `Slave` for interface ports.
    * `width`: The width of the port.  Only applicable for non-interface ports.
    * `connections`: A list of instanced IP ports that this port connects to.  Example: `gpio_0/GPIO2`
```yaml