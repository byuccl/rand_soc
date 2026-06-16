# Adding and Defining IP

This page describes how IP is defined in RandSoC and how to add a new IP block.
For the list of IP that already ships, see the "Supported IP" section of the
[README](../README.md). For how IP is loaded per Vivado version, see the IP and
version-system section of the [documentation index](index.md).

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
