# Adding and Defining IP

This page describes the IP RandSoC supports and how to add a new IP block. The
[Supported IP](#supported-ip) section below is the complete, canonical list. For
how IP is loaded per Vivado version, see the IP and version-system section of the
[documentation index](index.md).

## Supported IP

The registry that backs these tables is `import_ip()` in
[`rand_soc/creator.py`](../rand_soc/creator.py); keep them in sync when adding or
removing an IP.

### Randomized IP

These are the IP that can be drawn and randomly configured from a config's
`available_ip` list.

| Python Class | Description | Supported Configurations |
|---------|-------------|--------------------------|
|`Accumulator` | Xilinx *Accumulator* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/accumulator.html>) | Full configuration space |
|`AxiCan` | Xilinx *AXI CAN* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_can.html>) | Full configuration space, but untested as a separate license is required. |
|`AxiCdma` | Xilinx *AXI Central DMA Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_central_dma.html>) | Full configuration space |
|`AxiDma` | Xilinx *AXI Direct Memory Access* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_dma.html>) | Full configuration space (SG/direct/Micro/multichannel, MM2S+S2MM, control/status streams) |
|`AxiEthernetLite` | Xilinx *AXI Ethernet Lite* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_ethernetlite.html>) | Full configuration space |
|`AxiHwicap` | Xilinx *AXI Hardware ICAP* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_hwicap.html>) | Full configuration space |
|`AxiIic` | Xilinx *AXI IIC Bus Interface* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_iic.html>) | Full configuration space |
|`AxiQuadSpi` | Xilinx *AXI Quad SPI* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_quadspi.html>) | Full configuration space |
|`AxiTimer` | Xilinx *AXI Timer/Counter* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_timer.html>) | Full configuration space |
|`AxiUsb2Device` | Xilinx *AXI USB 2.0 Device Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_usb2_device.html>) | Full configuration space, but untested as a separate license is required. |
|`ConvolutionEncoder` | Xilinx *Convolution Encoder* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/convolution.html>) | Constraint length 3–9 with up to seven code vectors, optional puncturing (dual output, input/output rates, random puncture patterns), and optional TREADY/ACLKEN. |
|`ComplexMultiplier` | Xilinx *Complex Multiplier* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/complex-multiplier.html>) | Full configuration space: 8–63-bit per-operand widths, output width down to 2 bits, DSP (3/4-multiplier) or LUT construction, truncate/random rounding (with the CTRL/ROUND_CY channel), blocking/non-blocking flow and optimization goal, per-channel TLAST/TUSER (full 1–256-bit) with output TLAST behavior, and automatic or manual minimum latency. |
|`Cordic` | Xilinx *CORDIC* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/cordic.html>) | All functions (Rotate, Translate, Sin/Cos, Sinh/Cosh, Arc Tan, Arc Tanh, Square Root), word-serial/parallel architecture, pipelining modes, 8–48-bit input/output, rounding/scaling modes, optional coarse rotation and TLAST/TUSER. |
|`Dft` | Xilinx *Discrete Fourier Transform (DFT)* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/dft.html>) | Full configuration space |
|`Emc` | Xilinx *AXI External Memory Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_emc.html>) | Only number of banks. Other options not yet enumerated. |
|`Fft` | Xilinx *Fast Fourier Transform (FFT)* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/fast-fourier-transform.html>) | 1–12 channels, transform length 8–65536 (log2 3–16), the implementation options, and optional run-time-configurable transform length. Cyclic-prefix insertion is disabled. |
|`FloatingPoint` | Xilinx *Floating-Point Operator* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/floating-point-operator.html>) | All 15 operations (arithmetic, elementary functions, compare, and the fixed/float convert family) over Half/Single/Double/Custom plus the integer types, with the per-operation DSP-usage matrix, exception flags, per-channel TLAST/TUSER, and flow control. Latency is pinned to the core's maximum. |
|`Gpio` | Xilinx *AXI General Purpose IO* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_gpio.html>) | Full configuration space |
|`Microblaze` | Xilinx *AMD MicroBlaze™ Processor* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/microblaze.html>) | All configurations with local memory bus (No AXI DDR support) |
|`Uartlite` | Xilinx *AXI UART Lite* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_uartlite.html>) | Full configuration space |
|`XadcWiz` | Xilinx *XADC Wizard* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/xadc-wizard.html>) | Full configuration space |

### IP Added as Needed

These are not drawn from `available_ip`; the connection logic instances them as
the design requires (interconnect/clocking/interrupt infrastructure, the AXI-Stream
helpers, and the generic-wire glue built from `xlslice`/`xlconcat`).

| Python Class | Description |
|---------|-------------|
|`AxiSmartconnect` | Xilinx *AXI SmartConnect* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/smartconnect.html>) |
|`AxiInterconnect` | Xilinx *AXI Interconnect* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi-interconnect.html>) |
|`AxisBroadcaster` | Xilinx *AXI4-Stream Broadcaster* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi4-stream-infrastructure.html>) — fans one stream source out to multiple sinks. |
|`AxisCombiner` | Xilinx *AXI4-Stream Combiner* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi4-stream-infrastructure.html>) — merges multiple stream sources into one. |
|`AxisDwidthConverter` | Xilinx *AXI4-Stream Data Width Converter* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi4-stream-infrastructure.html>) — resolves TDATA width mismatches between a stream source and sink. |
|`ClkGen` | Xilinx *Clocking Wizard* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/clocking_wizard.html>) |
|`Intc` | Xilinx *AXI Interrupt Controller* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi_intc.html>) |
|`JtagAxi` | Xilinx *JTAG to AXI Master* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/jtag-to-axi-master.html>) — pin-free AXI master used by the no-master strategy. |
|`SystemReset` | Xilinx *Processor System Reset* (<https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/proc_sys_reset.html>) — the single design-wide reset. |
|`Reduce` | Generic-wire reducer built from `xlslice`/`xlconcat` primitives; narrows a wide signal down to a smaller sink. |
|`SliceAndConcat` | Generic-wire glue built from `xlslice`/`xlconcat` primitives; drives a port from one or more narrower drivers. |

## Two kinds of IP

- **YAML-driven IP** (`IPrandom`) — the common case. A small Python class points
  at a sibling `.yaml` file that describes the inner Xilinx IP, its randomizable
  parameters, ports, and internal wiring. Most peripherals (GPIO, UART, FFT, …)
  work this way.
- **Hand-built IP** (`IP`) — for IP that is instanced mid-flow by the connection
  logic and constructed programmatically (the AXIS broadcaster, combiner, width
  converter, and the JTAG-to-AXI master). These build their hierarchy pins
  directly in Python instead of from YAML.

Each IP lives under [`rand_soc/ip/<version>/`](../rand_soc/ip/) (e.g. `v2020_2`,
`v2024_2`); `import_ip()` loads it from the configured `vivado_version` with
fallback to older versions, so a single shared copy serves all versions unless a
version-specific variant overrides it.

## Adding a YAML-driven IP

### 1. The Python class

Add a class in `rand_soc/ip/<version>/`. Example, `Gpio`:

```python
from .ip_base import IPrandom

class Gpio(IPrandom):
    @property
    def name(self):
        return "gpio"

    def randomize(self):
        self.load_data_from_yaml(__file__)
```

Then register it in the `import_ip()` table in
[`rand_soc/creator.py`](../rand_soc/creator.py) so it can be referenced by class
name from a config's `available_ip`.

### 2. The YAML file

Add a `.yaml` next to the class (same base name). It lists the Xilinx IP to
instantiate as part of this logical IP — usually one, but it may be several (e.g.
`Microblaze` bundles its processor plus local-memory blocks). Each entry contains:

- `id` — a unique identifier for the inner IP. Example: `"gpio_0"`.
- `definition` — the IP VLNV. Example: `"xilinx.com:ip:axi_gpio:2.0"`.
- `configuration` — a list of parameters. Each item may have:
  - `name` — the parameter name (e.g. `"C_GPIO_WIDTH"`).
  - `internal` — `true` if the parameter is only used inside RandSoC (for `enable`
    expressions etc.) and should *not* be passed to Vivado.
  - `values` — a list of possible values, chosen at random. Example: `["I", "O", "IO"]`.
  - `values_eval` — like `values`, but a Python expression evaluated by the tool
    with access to earlier parameters and helpers such as `all_ones()`,
    `randintwidth()`, `range()`, `math`. Example: `range(1,33)`.
  - `value` / `value_eval` — a single fixed (or evaluated) value instead of a list.
  - `enable` — a boolean expression; the parameter is only included when it is
    true. Example: `"C_IS_DUAL and (direction == 'I')"`.
  - `format` — value formatting, e.g. `hex`.
- `ports` — ports of the inner IP exposed to the rest of the design. Each entry:
  - `name` — the exposed port name (e.g. `GPIO2`).
  - `protocol` — a Xilinx interface VLNV (e.g.
    `xilinx.com:interface:gpio_rtl:1.0`) or a RandSoC protocol (`clk`, `reset`,
    `irq`, `data`, `control`). New Xilinx protocols must be added to the
    `Protocol` enum in [`typedefs.py`](../rand_soc/typedefs.py).
  - `direction` — `I`/`O` for wire ports, `Master`/`Slave` for interface ports.
  - `width` — width in bits (wire ports only).
  - `connections` — inner IP pins this port connects to. Example: `gpio_0/GPIO2`.
  - `addr_seg_name` — for an AXI slave, its address segment (e.g.
    `gpio_0/S_AXI/Reg`).
  - `enable` — only expose the port when this expression is true.
- `internal_connections` — for multi-IP definitions, wiring between the inner IP
  (e.g. a processor to its memory). See `microblaze.yaml` for an example.

### Complete example (`gpio.yaml`)

```yaml
- id: "gpio_0"
  definition: "xilinx.com:ip:axi_gpio:2.0"
  configuration:
  - name: direction
    internal: true
    values: ["I", "O", "IO"]

  - name: C_GPIO_WIDTH
    values_eval: range(1,33)

  - name: C_ALL_INPUTS
    enable: "direction == 'I'"
    value: 1

  - name: C_TRI_DEFAULT
    values_eval: "[0, all_ones(C_GPIO_WIDTH), randintwidth(C_GPIO_WIDTH)]"
    enable: "direction == 'IO'"
    format: hex

  - name: C_INTERRUPT_PRESENT
    values: [true, false]

  ports:
  - name: GPIO
    protocol: "xilinx.com:interface:gpio_rtl:1.0"
    direction: Master
    connections:
    - gpio_0/GPIO
  - name: clk
    protocol: clk
    direction: I
    width: 1
    connections:
    - gpio_0/s_axi_aclk
  - name: rst
    protocol: reset_peripheral_n
    direction: I
    width: 1
    connections:
    - gpio_0/s_axi_aresetn
  - name: AXI
    protocol: "xilinx.com:interface:aximm_rtl:1.0"
    direction: Slave
    connections:
    - gpio_0/S_AXI
    addr_seg_name: "gpio_0/S_AXI/Reg"
  - name: irq
    protocol: irq
    direction: O
    width: 1
    connections:
    - gpio_0/ip2intc_irpt
    enable: C_INTERRUPT_PRESENT
```

(See the full [`gpio.yaml`](../rand_soc/ip/v2020_2/gpio.yaml) for the complete
dual-channel configuration.)

## Adding a hand-built IP

For IP instanced by the connection logic, subclass `IP` and build the pins
directly. The AXIS [`axis_broadcaster.py`](../rand_soc/ip/v2020_2/axis_broadcaster.py),
[`axis_dwidth_converter.py`](../rand_soc/ip/v2020_2/axis_dwidth_converter.py), and
[`jtag_axi.py`](../rand_soc/ip/v2020_2/jtag_axi.py) are the templates: instance the
Xilinx IP with `_new_instance()`, create hierarchy pins with `_create_hier_pin()`,
and connect them inward with `connect_internal()`. Clock/reset pins are picked up
automatically by the creator's clock/reset passes.
