# RandSoC Documentation

RandSoC generates random, synthesizable System-on-Chip designs as Xilinx Vivado
Tcl scripts. It randomly selects and configures Xilinx IP, connects them with a
randomized but legal interconnect topology, and emits a `design.tcl` that builds
(and optionally synthesizes) the design in Vivado. It is intended for producing
large datasets of realistic synthetic hardware for ML, CAD research, and tool
testing.

This is the documentation index. See also:

- **[Configuration File Reference](config.md)** — every key the config YAML accepts.
- **[AXI4-Stream Connection](axi_stream.md)** — how stream IP are wired (the
  source/sink assignment algorithm, broadcasters, combiners, width converters).
- **[Adding and Defining IP](ip.md)** — the IP YAML schema, how to add a new IP
  block, and the complete [Supported IP](ip.md#supported-ip) list.
- The repository [`README.md`](../README.md) — install/dependencies and a project
  overview.

## Running the tool

### Command line

```bash
python main.py <output_dir> <config.yaml> [--seed N] [--part PART] [--no-synth]
```

- `output_dir` — where `design.tcl` (and `design.yaml`, logs, constraints) are written.
- `config.yaml` — the randomization config (see [config.md](config.md)).
- `--seed` — RNG seed; the same seed + config + part reproduces a design exactly.
- `--part` — Xilinx part (e.g. `xc7a200tlffv1156-2L`).
- `--no-synth` — stop the generated Tcl after block-design creation/validation,
  skipping synthesis (a fast check that the design itself is valid).

### Python

```python
from rand_soc.creator import RandomDesign

design = RandomDesign(output_dir, config_path, seed, part, synthesize=True)
design.create()   # build the design in memory
design.write()    # write design.tcl + design.yaml
```

### Makefile targets

The [`Makefile`](../Makefile) wraps common flows. Key variables:
`CONFIG` (config yaml), `PART`, `SEED`, `VIVADO` (vivado path), `HOST` (remote
host, default `CCL1`), `JOBS`, `N` (design count), `SYNTH`, `TIMEOUT`.

| Target | What it does |
|--------|--------------|
| `make run` | Generate a full (synthesis-enabled) `design.tcl` into `./temp`. |
| `make run-bd` | Generate a `--no-synth` `design.tcl` (stops after BD validation). |
| `make vivado` | Run `temp/design.tcl` through local Vivado. |
| `make vivado-bd` | `run-bd` then run it through Vivado (validate only, no synth). |
| `make smoke` | Build `N` random designs through **Tcl creation only** (no Vivado) — fast first-pass check. |
| `make vivado-test` | Build `N` designs and run them through Vivado on a remote host up to BD validation. Add `SYNTH=1` for full synthesis (passes only if `synth.dcp` is produced); raise `TIMEOUT` and lower `JOBS` for synthesis. |

Examples:

```bash
make smoke CONFIG=fft_config.yaml N=50
make vivado-test CONFIG=fft_config.yaml N=100
make vivado-test CONFIG=fft_config.yaml N=50 SYNTH=1 TIMEOUT=3600 JOBS=20
```

The standalone harnesses are [`smoke_test.py`](../smoke_test.py) (parallel
Tcl-creation check) and [`vivado_test.py`](../vivado_test.py) (remote Vivado
validation/synthesis with a progress bar and per-seed logs under
`temp/vivado_test/`).

## How it works

The generator lives in [`rand_soc/creator.py`](../rand_soc/creator.py)
(`RandomDesign`). At a high level `create()`:

1. Loads the config and resolves the IP version set (`import_ip()`).
2. Randomly draws `min_ip..max_ip` IP from `available_ip` and randomizes each
   IP's configuration.
3. Runs `_ports()` — a fixed-point loop that repeatedly sweeps the
   still-unconnected ports and connects them by protocol, until everything is
   handled. Each sweep runs the connection passes:
   - `_resets()` / `_clocks()` — single external reset + a clock wizard.
   - `_external_interfaces()` — generic Xilinx interfaces (GPIO, UART, …) are
     brought to the top level.
   - `_interrupts()` — interrupt controller wiring.
   - `_axi()` — the memory-mapped AXI network (interconnect/smartconnect,
     masters, slaves). The **no-master strategy** (`axi_mm.no_master`) is applied
     here.
   - `_axi_stream()` — the AXI-Stream network (see [axi_stream.md](axi_stream.md)),
     where **width converters** (`axi_stream.*_converters`) are inserted.
   - `_generic_ports()` — leftover scalar data/control wires.

   The loop design means infrastructure IP added by one pass (e.g. a broadcaster
   or width converter) has its own clock/reset pins picked up by a later sweep.
4. Renders the accumulated block-design Tcl into
   [`run.tcl.mustache`](../rand_soc/run.tcl.mustache), which adds
   `assign_bd_address`, `validate_bd_design`, the Vivado-version guard, and the
   (optional) synthesis section.

### IP and the version system

Each IP is a Python class under [`rand_soc/ip/<version>/`](../rand_soc/ip/).
Most are **yaml-driven** (`IPrandom` + a sibling `.yaml` describing the inner
Xilinx IP, its randomizable parameters, ports, and internal connections); a few
are **hand-built** (`IP` subclasses that construct hierarchy pins directly), such
as the AXIS broadcaster, combiner, width converter, and JTAG-to-AXI master.

`import_ip()` loads each IP from the configured `vivado_version` directory,
falling back to older versions when a given version lacks that module. This lets
a version-specific variant override the base while unchanged IP fall through to a
single shared copy.

To add new IP, see [Adding and Defining IP](ip.md).
