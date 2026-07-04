from collections import defaultdict
import logging
import math
import pathlib
import random
import sys
import yaml
import chevron
import importlib

from .paths import ROOT_PATH
from .ports import ExternalPort
from .port_assigner import port_assigner_axis, port_assigner_random
from .typedefs import ConverterReq, Direction, NetType, Protocol


def import_ip(version, versions):
    ips = [
        ("reset", ["SystemReset"]),
        ("reduce", ["Reduce"]),
        ("slice_and_concat", ["SliceAndConcat"]),
        ("accumulator", ["Accumulator"]),
        ("axi", ["AxiSmartconnect", "AxiInterconnect"]),
        ("axi_cdma", ["AxiCdma"]),
        ("axi_dma", ["AxiDma"]),
        ("axi_hwicap", ["AxiHwicap"]),
        ("axi_timer", ["AxiTimer"]),
        ("axi_usb2_device", ["AxiUsb2Device"]),
        ("clk_gen", ["ClkGen"]),
        ("dft", ["Dft"]),
        ("intc", ["Intc"]),
        ("uartlite", ["Uartlite"]),
        ("emc", ["Emc"]),
        ("gpio", ["Gpio"]),
        ("microblaze", ["Microblaze"]),
        ("xadc_wiz", ["XadcWiz"]),
        ("axi_can", ["AxiCan"]),
        ("axi_ethernet_lite", ["AxiEthernetLite"]),
        ("axi_iic", ["AxiIic"]),
        ("axi_quad_spi", ["AxiQuadSpi"]),
        ("jtag_axi", ["JtagAxi"]),
        # AXI Stream IP (axi-stream branch)
        ("fft", ["Fft"]),
        ("axis_broadcaster", ["AxisBroadcaster"]),
        ("axis_combiner", ["AxisCombiner"]),
        ("axis_dwidth_converter", ["AxisDwidthConverter"]),
        ("cordic", ["Cordic"]),
        ("convolution", ["ConvolutionEncoder"]),
        ("floating_point", ["FloatingPoint"]),
        ("complex_multiplier", ["ComplexMultiplier"]),
    ]
    versions = versions[versions.index(version) :]
    for lib, ips in ips:
        for v in versions:
            name = f".ip.{v}.{lib}"
            canonical = f".ip.{lib}"
            try:
                module = importlib.import_module(name, __package__)
                sys.modules[canonical] = module
                for cls_name in ips:
                    cls = getattr(module, cls_name, None)
                    if not cls:
                        logging.warning("%s not found in %s", cls_name, name)
                    globals()[cls_name] = cls
                break
            except ModuleNotFoundError:
                continue


class RandomDesign:
    """Creates a random design"""

    def __init__(
        self, output_dir_path, config_path=None, seed=None, part=None, synthesize=True
    ):
        if config_path is None:
            config_path = ROOT_PATH / "creator.yaml"

        # When False, the generated Tcl stops after the block design is built and
        # validated, skipping synthesis (fast Vivado check of the design itself).
        self.synthesize = synthesize

        # Enable logging
        self._output_dir_path = pathlib.Path(output_dir_path).resolve()
        log_file = self._output_dir_path / "log.txt"
        self._output_dir_path.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=log_file,
            filemode="w",
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.DEBUG,
        )

        # Set random seed
        self.seed = seed
        if self.seed is not None:
            random.seed(self.seed)
            logging.info(f"Using seed: {self.seed}")

        if part is None:
            part = "xc7a200tsbg484-1"
        self.part = part
        self.config_path = config_path

        self.tcl_str = ""
        self.impl_constraints_tcl = ""

        # Block diagram string
        self._bd_tcl = ""
        self.ip_to_ip_connections_tcl = "\n########## IP to IP connections ##########\n"
        self._addr_space_tcl = "\n########## Address space ##########\n"
        self.ip = []
        self._pi_ports = {}
        self._po_ports = {}
        self.port_types_initialized = set()
        self._ip_idx = 0
        self._axi_complete = False
        self._axis_complete = False
        self._intc_complete = False
        self._reset_inst = None
        self._clk_wiz_inst = None
        self._randomized_signal_drivers = {}

        # AXIS width verification: (inner_ip_pin, declared_width, label) entries,
        # registered by IpPort.connect_internal for every AXI-Stream hier pin. The
        # template emits a post-validate Tcl check comparing each IP's resolved
        # TDATA width to the width the generator declared.
        self._width_checks = []

        # Config-driven strategy knobs (populated from the config in create()).
        self._axi_mm_no_master = ["external"]
        self._axis_io_conv = "random"
        self._axis_internal_conv = "random"

    def register_width_check(self, inner_pin, declared_width, label):
        """Record an AXI-Stream pin whose IP-resolved TDATA width should be
        verified against the width the generator declared. Emitted as Tcl by
        _render_width_checks() and run after validate_bd_design."""
        self._width_checks.append((inner_pin, declared_width, label))

    def _render_width_checks(self):
        """Tcl that prints, for each registered AXIS pin, the IP's resolved TDATA
        width vs the declared width as a grep-able RANDSOC_WIDTH_CHECK line. Each
        check is wrapped in catch so a missing property never aborts the run."""
        if not self._width_checks:
            return ""
        lines = ["\n########## AXIS width verification ##########"]
        for inner, width, label in self._width_checks:
            lines.append(
                f"if {{[catch {{\n"
                f"  set __aw [expr {{[get_property CONFIG.TDATA_NUM_BYTES "
                f"[get_bd_intf_pins {inner}]] * 8}}]\n"
                f'  set __s [expr {{$__aw == {width} ? "OK" : "MISMATCH"}}]\n'
                f'  puts "RANDSOC_WIDTH_CHECK {label} declared={width} actual=$__aw $__s"\n'
                f'}} __err]}} {{ puts "RANDSOC_WIDTH_CHECK {label} declared={width} actual=ERR $__err" }}'
            )
        return "\n".join(lines) + "\n"

    def write(self):
        """Write the design tcl and impl_constraints tcl to files"""
        output_file_path = self._output_dir_path / "design.tcl"
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(self.tcl_str)

        impl_constraints_tcl_path = self._output_dir_path / "impl_constraints.tcl"
        with open(impl_constraints_tcl_path, "w", encoding="utf-8") as f:
            f.write(self.impl_constraints_tcl)

        # Write the IP randomization to a yaml file
        ip_yaml_path = self._output_dir_path / "design.yaml"
        random_data = {
            "randsoc_seed": self.seed,
            "ip": [
                {
                    "randsoc_class": ip.__class__.__name__,
                    "instance_name": ip.hier_name,
                    "vivado_ip": [
                        {
                            "vivado_ip_type": module_inst.ip_name,
                            "instance_name": module_inst.instance_name,
                            "properties": module_inst.properties,
                        }
                        for module_inst in ip.module_instances.values()
                    ],
                }
                for ip in sorted(self.ip, key=lambda ip: ip.__class__.__name__)
                if not isinstance(ip, (Reduce, SliceAndConcat))
            ],
            "primary_inputs": [
                {"name": pi.name, "protocol": pi.protocol, "width": pi.width}
                for pi in sorted(self._pi_ports.values(), key=lambda x: x.name)
            ],
            "primary_outputs": [
                {"name": po.name, "protocol": po.protocol, "width": po.width}
                for po in sorted(self._po_ports.values(), key=lambda x: x.name)
            ],
            "randomized_signal_drivers": dict(self._randomized_signal_drivers),
        }

        with open(ip_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(random_data, f, sort_keys=False)

    def get_yaml_available_ip(self, yaml_file):
        """Retrieves and returns list of IP objects given in yaml"""
        ip_list = yaml_file["available_ip"]
        for ip in ip_list:
            assert "class" in ip, f"IP {ip} does not have a class"
            ip["class"] = getattr(sys.modules[__name__], ip["class"])
        return ip_list

    def get_creator_yaml(self):
        """Helper method for retrieving creator configuration data"""
        yaml_path = self.config_path
        assert yaml_path.is_file(), f"Rand_soc config file {yaml_path} does not exist"
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f)

    def create(self):
        """Create the design tcl"""
        project_config = {
            "part": self.part,
            "bd_name": "bd_design",
            "checkpoint_path": "synth.dcp",
            "verilog_path": "synth.v",
            "edif_path": "viv_synth.edf",
            "top": "bd_design_wrapper",
            "io_report_path": "report_io.txt",
            "utilization_path": "synth_utilization.txt",
            "synthesize": self.synthesize,
        }

        # env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        template_path = ROOT_PATH / "run.tcl.mustache"
        assert template_path.is_file(), f"Template file {template_path} does not exist"
        with open(template_path, "r") as f:
            template = f.read()

        creator_yaml = self.get_creator_yaml()

        vivado_version = creator_yaml.get("vivado_version", "v2022_2")
        import_ip(
            vivado_version,
            ["v2024_2", "v2022_2", "v2020_2"],
        )
        # Vivado version this design targets (e.g. "v2024_2" -> "2024.2"); the
        # generated Tcl checks the running Vivado matches, since IP VLNVs are
        # version-specific and a mismatch otherwise yields cryptic errors.
        project_config["vivado_version"] = vivado_version.lstrip("v").replace("_", ".")

        # AXI-MM no-master strategy: when a design has no internal AXI master, one
        # of these options is chosen at random to provide one. "external" brings a
        # top-level AXI port to package pins (default/legacy); "jtag" instances a
        # pin-free JTAG-to-AXI master. Default is external-only.
        self._axi_mm_no_master = creator_yaml.get("axi_mm", {}).get(
            "no_master", ["external"]
        )

        # AXIS data-width-converter policies. "yes" inserts a converter on every
        # width mismatch, "no" never does, "random" decides per connection. YAML
        # parses bare yes/no as booleans, so normalize those back to strings.
        def _norm_conv_policy(value):
            if value is True:
                return "yes"
            if value is False:
                return "no"
            assert value in ("yes", "no", "random"), (
                f"axi_stream converter policy must be yes/no/random, got {value!r}"
            )
            return value

        axi_stream_cfg = creator_yaml.get("axi_stream") or {}
        self._axis_io_conv = _norm_conv_policy(
            axi_stream_cfg.get("io_converters", "random")
        )
        self._axis_internal_conv = _norm_conv_policy(
            axi_stream_cfg.get("internal_converters", "random")
        )

        min_ip = creator_yaml["min_ip"]
        max_ip = creator_yaml["max_ip"]
        ip_list = self.get_yaml_available_ip(creator_yaml)

        # Select AXI type
        axi_type_names = creator_yaml.get("axi_types", ["AxiSmartconnect"])
        axi_type_map = {
            "AxiSmartconnect": AxiSmartconnect,
            "AxiInterconnect": AxiInterconnect,
        }
        axi_types = [axi_type_map[name] for name in axi_type_names]
        self._axi_class = random.choice(axi_types)
        logging.info(f"AXI type: {self._axi_class.__name__}")

        num_ip = random.randint(min_ip, max_ip)
        logging.info("########## Selecting IPs ##########")
        for i in range(num_ip):
            while True:
                ip = random.choice(ip_list)
                if "max" in ip:
                    if ip["max"] == 0:
                        continue
                    ip["max"] -= 1
                break

            ip_type = ip["class"]
            logging.info(f"IP {i}: {ip_type.__name__}")
            self._new_ip(ip_type)

        for ip in self.ip:
            ip.randomize()
            ip.instance()

        self._ports()

        ip_str = "".join([ip.bd_str for ip in self.ip])

        self._bd_tcl = (
            ip_str + self._bd_tcl + self.ip_to_ip_connections_tcl + self._addr_space_tcl
        )

        project_config["block_diagram"] = self._bd_tcl
        project_config["width_checks"] = self._render_width_checks()
        self.tcl_str = chevron.render(template, project_config)

        for ip in self.ip:
            self.impl_constraints_tcl += ip._impl_constraints_tcl

    def _ports(self):
        unhandled_ports = set()
        disconnected_ports_old = set()

        while True:
            if len(unhandled_ports) > 1000:
                logging.info(
                    "Too many unhandled ports - endless loop of port creation?"
                )
                sys.exit(1)

            # Get disconnected ports, that we haven't previously ignored.
            # If there are no more ports to handle, exit the loop.
            disconnected_ports = set(
                p
                for ip in self.ip
                for p in ip.ports
                if (not p.connected) and (not p in unhandled_ports)
            )
            if len(disconnected_ports) == 0:
                break

            # Ignore ports that are still disconnected from last iteration
            for p in disconnected_ports:
                if p in disconnected_ports_old:
                    unhandled_ports.add(p)

            disconnected_ports_old = disconnected_ports

            # Reset ports
            self._resets()

            # Clock ports
            self._clocks()

            # GPIO, UART, USB2, ICAP ports
            self._external_interfaces()

            # Interrupt ports
            self._interrupts()

            # AXI memory-mapped ports
            self._axi()

            # AXI Stream ports
            self._axi_stream()
            # xilinx.com:ip:axis_broadcaster:1.1
            # xilinx.com:ip:axis_combiner:1.1
            # self._generic_ports(
            #     protocol=Protocol.AXI_STREAM,
            #     max_randomly_generated_inputs=0,
            #     max_randomly_generated_outputs=0,
            # )

            # Data and control ports
            self._generic_ports(
                protocol=Protocol.DATA,
                max_randomly_generated_inputs=128,
                max_randomly_generated_outputs=32,
            )
            self._generic_ports(
                protocol=Protocol.CONTROL,
                max_randomly_generated_inputs=8,
                max_randomly_generated_outputs=8,
            )

        logging.info("")
        for port in unhandled_ports:
            logging.error("Unhandled port: %s", port)
        assert not unhandled_ports

    def _axi_stream(self):
        """Connect AXI Stream ports"""

        if self._axis_complete:
            return

        # If no IP in the design has any AXI Stream ports, there is no stream
        # network to build. Skip the stage rather than fabricating external
        # source/sink ports that have nothing to connect to.
        if not any(ip.has_axis_ports() for ip in self.ip):
            logging.info("No AXI Stream ports in design, skipping AXI Stream stage")
            return

        logging.info("########## AXI Stream ##########")

        assert not self._axis_complete
        self._axis_complete = True

        # Make sure we have a source IP, if not, create an external interface
        # Source IP have no input AXI Stream ports, only output ports
        primary_source_ips = [
            ip
            for ip in self.ip
            if ip.has_axis_master_ports() and not ip.has_axis_slave_ports()
        ]
        primary_sources = [
            port
            for ip in primary_source_ips
            for port in ip.ports
            if port.protocol == Protocol.AXI_STREAM
            and port.direction == Direction.OUTPUT
        ]
        if not primary_sources:
            # A single external source is enough to seed the network; the
            # assigner will broadcast it if it needs to drive multiple sinks.
            primary_sources.append(
                self._create_external_port(
                    "external_axis_source",
                    Protocol.AXI_STREAM,
                    Direction.INPUT,
                    width=8,
                )
            )

        # Make sure we have a sink IP, if not, create an external interface
        # Sink IP have no output AXI Stream ports, only input ports
        primary_sink_ips = [
            ip
            for ip in self.ip
            if ip.has_axis_slave_ports() and not ip.has_axis_master_ports()
        ]
        primary_sinks = [
            port
            for ip in primary_sink_ips
            for port in ip.ports
            if port.protocol == Protocol.AXI_STREAM
            and port.direction == Direction.INPUT
        ]
        if not primary_sinks:
            primary_sinks.append(
                self._create_external_port(
                    "external_axis_sink", Protocol.AXI_STREAM, Direction.OUTPUT, width=8
                )
            )

        # Find all internal AXI Stream IP
        internal_axis_ips = [
            ip
            for ip in self.ip
            if ip not in primary_source_ips
            and ip not in primary_sink_ips
            and ip.has_axis_ports()
        ]

        assignments = port_assigner_axis(
            primary_sources, primary_sinks, internal_axis_ips
        )
        for in_port, drivers in assignments.items():
            logging.info(f"AXI Stream port {in_port.hier_name_w} driven by:")
            for driver in drivers:
                logging.info(f"  {driver.hier_name_w}")

        self._port_connector(Protocol.AXI_STREAM, assignments)

    def _generic_ports(
        self, protocol, max_randomly_generated_inputs, max_randomly_generated_outputs
    ):
        """Connect data ports."""
        assert protocol in Protocol

        if protocol in self.port_types_initialized:
            return
        self.port_types_initialized.add(protocol)

        logging.info(f"########## Connecting {protocol} ports ##########")
        self._bd_tcl += f"\n########## Connecting {protocol} ports ##########\n"
        out_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == protocol
            and not p.connected
            and p.direction == Direction.OUTPUT
        ]
        in_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == protocol
            and not p.connected
            and p.direction == Direction.INPUT
        ]
        # for p in in_ports:
        #     print(p.name, p.direction, p.width)
        num_in_pins = sum(p.width for p in in_ports)
        num_out_pins = sum(p.width for p in out_ports)

        # Create primary inputs for data (primary input is an output)
        #
        # At most max_randomly_generated_inputs will be created (unless num_in_pins is less than that,
        # in which case the maximum number of inputs will be num_in_pins)
        #
        # If there are no output pins, then at least one primary input will be created
        if protocol not in self._pi_ports:
            min_pis = 0
            max_pis = max_randomly_generated_inputs

            # If there are no output pins, then at least one primary input will be created
            if num_out_pins == 0 and num_in_pins > 0:
                min_pis = 1

            # Don't create more primary inputs than there are input pins
            max_pis = min(max_pis, num_in_pins)

            # Don't create too many I/O ports
            # If we already have more outputs than inputs, then don't create more PIs
            max_pis = min(max_pis, max(0, num_in_pins - num_out_pins))

            pi_width = random.randint(min_pis, max_pis)
            if pi_width:
                sig_name = f"{protocol.value}_I"
                logging.info(
                    f"Creating primary input port: {sig_name}, width: {pi_width}"
                )
                new_port = self._create_external_port(
                    sig_name, protocol, Direction.INPUT, pi_width
                )
                self._pi_ports[protocol] = new_port
                out_ports.insert(0, new_port)
                num_out_pins = sum(p.width for p in out_ports)

        # Create primary outputs for data (primary output is an input)
        #
        # This will only be done if there are more outputs than inputs,
        # to prevent unused outputs
        if num_out_pins > num_in_pins:
            out_pins_needed = num_out_pins - num_in_pins

            if out_pins_needed > max_randomly_generated_outputs:
                po_width = max_randomly_generated_outputs
            else:
                po_width = out_pins_needed

            sig_name = f"{protocol.value}_O"
            logging.info(f"Creating primary output port: {sig_name}, width: {po_width}")
            new_port = self._create_external_port(
                sig_name, protocol, Direction.OUTPUT, po_width
            )
            self._po_ports[protocol] = new_port

            if po_width < out_pins_needed:
                logging.info(f"Adding reducer from {out_pins_needed} to {po_width}")
                reducer = self._new_ip(Reduce, (protocol, out_pins_needed, po_width))
                in_ports.append(reducer.in_port)
                reducer.out_port.connect(new_port)
            else:
                in_ports.append(new_port)
            num_in_pins = sum(p.width for p in in_ports)

        logging.info(f"Num input pins: {num_in_pins}")
        for p in in_ports:
            logging.info(f"  {p.hier_name} {p.width}")
        logging.info(f"Num output pins: {num_out_pins}")
        for p in out_ports:
            logging.info(f"  {p.hier_name} {p.width}")

        # Make the connection assignments
        self._randomized_signal_drivers[protocol] = port_assigner_random(
            in_ports, out_ports
        )

        # Make the connections
        self._port_connector(protocol, self._randomized_signal_drivers[protocol])

    def _port_connector(self, protocol, driver_map):
        """Make multiple port connections for a given protocol.  The driver_map is a
        dictionary mapping each in_port to a list of (out_port, high_bit, low_bit) tuples.
        """
        if protocol == Protocol.AXI_STREAM:
            self._axi_stream_connector(driver_map)
        else:
            for in_port, drivers in driver_map.items():
                self._connect_multiple_drivers_to_port(in_port, drivers)

    def _connect_multiple_drivers_to_port(self, port, drivers):
        """Connect multiple drivers to a port
        This function only supports wire ports, not interface ports.
        """
        assert port.protocol.get_type() == NetType.WIRE
        self._new_ip(SliceAndConcat, (port, drivers))

    def _clocks(self):
        clock_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol in (Protocol.CLOCK, Protocol.CLOCK_LOCKED)
            and not p.connected
            and p.direction == Direction.INPUT
        ]

        # Create single external clock
        logging.info("########## Clocks ##########")
        self._bd_tcl += "\n########## Clocks ##########\n"
        if self._clk_wiz_inst is None:
            self._clk_wiz_inst = self._new_ip(ClkGen)
            logging.info("Creating external clock port: clock")
            self._create_external_port(
                "clk", Protocol.CLOCK, Direction.INPUT, width=1
            ).connect(self._clk_wiz_inst.port_clk_in)

        for clock_input in clock_inputs:
            if clock_input.protocol == Protocol.CLOCK_LOCKED:
                driver = self._clk_wiz_inst.port_dcm_locked
            elif clock_input.protocol == Protocol.CLOCK:
                driver = self._clk_wiz_inst.port_clk_out
            else:
                logging.error(
                    f"Unexpected clock input protocol: {clock_input.protocol}"
                )
            logging.info(f"Connecting {clock_input.hier_name} to {driver.hier_name}")
            driver.connect(clock_input)

    def _resets(self):
        logging.info("########## Resets ##########")
        # Instance system reset
        if self._reset_inst is None:
            self._reset_inst = self._new_ip(SystemReset)

        # Create single external reset
        if Protocol.RESET not in self._pi_ports:
            self._bd_tcl += "\n########## Resets ##########\n"
            logging.info("Creating external reset port: reset")
            self._pi_ports[Protocol.RESET] = self._create_external_port(
                "reset", Protocol.RESET, Direction.INPUT, 1
            )

        reset_sources_by_protocol = {
            Protocol.RESET: self._pi_ports[Protocol.RESET],
            Protocol.RESET_MICROBLAZE: self._reset_inst.port_mb_reset,
            Protocol.RESET_INTERCONNECT: self._reset_inst.port_interconnect_aresetn,
            Protocol.RESET_PERIPHERAL: self._reset_inst.port_peripheral_reset,
            Protocol.RESET_PERIPHERAL_N: self._reset_inst.port_peripheral_areset_n,
        }

        # Collect unconnected reset inputs
        reset_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol in reset_sources_by_protocol
            and not p.connected
            and p.direction == Direction.INPUT
        ]

        for reset_input in reset_inputs:
            logging.info(
                f"Connecting {reset_input} to reset source {reset_sources_by_protocol[reset_input.protocol]}"
            )
            reset_sources_by_protocol[reset_input.protocol].connect(reset_input)

    def _interrupts(
        self,
    ):
        interrupt_outputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == Protocol.IRQ
            and not p.connected
            and p.direction == Direction.OUTPUT
        ]
        interrupt_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == Protocol.MB_INTERRUPT
            and not p.connected
            and p.direction == Direction.INPUT
        ]

        if not interrupt_outputs and not interrupt_inputs:
            return

        logging.info("########## Interrupts ##########")
        logging.info(f"Interrupt outputs: {len(interrupt_outputs)}")
        logging.info(f"Interrupt inputs: {len(interrupt_inputs)}")

        if not interrupt_outputs:
            for interrupt_input in interrupt_inputs:
                logging.info(f"Ignoring interrupt input: {interrupt_input}")
                interrupt_input.connected = True
            return

        # Incremental interrupts not supported
        assert not self._intc_complete
        self._intc_complete = True

        # If there are no microblaze interrupt inputs, create a top-level output
        if not interrupt_inputs:
            irq_out = self._create_external_port(
                "irq", Protocol.MB_INTERRUPT, Direction.OUTPUT
            )
            interrupt_inputs.append(irq_out)

        self._bd_tcl += "\n########## Interrupts ##########\n"
        for interrupt_input in interrupt_inputs:
            intc = self._new_ip(Intc, (len(interrupt_outputs),))
            for i, interrupt_output in enumerate(interrupt_outputs):
                intc.input_ports[i].connect(interrupt_output)
            interrupt_input.connect(intc.port_irq)

    # Interface protocols that have their own dedicated connection handling and
    # must NOT be blindly exported to the top level.
    _SPECIALLY_HANDLED_INTERFACES = (
        Protocol.AXI_STREAM,
        Protocol.AXI_MM,
        Protocol.MB_INTERRUPT,
    )

    def _external_interfaces(self):
        # Any remaining unconnected Xilinx interface port (GPIO, UART, EMC, ULPI,
        # ICAP/arb, XADC diff IO, CAN, IIC, MII/MDIO, SPI, startup, ...) is simply
        # brought out to the top level. Interfaces with dedicated handling are
        # excluded.
        ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol.get_type() == NetType.INTERFACE
            and p.protocol not in self._SPECIALLY_HANDLED_INTERFACES
            and not p.connected
        ]

        # Create external outputs
        self._bd_tcl += "\n########## GPIO, UART ##########\n"
        for port in ports:
            self._create_external_port(
                f"{port.ip.hier_name}_{port.name}", port.protocol, port.direction
            ).connect(port)

    def _axi_stream_connector(self, driver_map):
        """Build AXI Stream connections.

        ``driver_map`` maps each sink port to a list of source (driver) ports.

        - A driver that feeds more than one sink gets an AXI Stream Broadcaster
          (1 source -> N sinks); each sink connects to a distinct output.
        - A sink fed by more than one driver gets an AXI Stream Combiner
          (N sources -> 1 sink); each driver connects to a distinct input.
        """
        fanout_degree = defaultdict(int)
        fanout_next_idx = defaultdict(int)
        broadcasters = {}

        # Count how many sinks each driver feeds (fanout)
        for in_port, drivers in driver_map.items():
            for driver in drivers:
                fanout_degree[driver] += 1

        # Create a broadcaster for each driver that feeds more than one sink
        for driver, degree in fanout_degree.items():
            if degree > 1:
                broadcasters[driver] = self._new_ip(AxisBroadcaster, (driver, degree))

        def source_port_for(driver):
            """Resolve the port that should actually drive a sink input for this
            driver, inserting a broadcaster output when the driver fans out."""
            if fanout_degree[driver] > 1:
                idx = fanout_next_idx[driver]
                fanout_next_idx[driver] += 1
                return broadcasters[driver].get_output_port(idx)
            return driver

        for in_port, drivers in driver_map.items():
            if len(drivers) == 1:
                # Single driver: connect the sink to its (resolved) source,
                # inserting a width converter if needed.
                self._connect_axis(source_port_for(drivers[0]), in_port)
            else:
                # Multiple drivers: merge them into the sink with a combiner. Each
                # combiner input is created at its driver's width, so no converter
                # is needed on these legs.
                combiner = self._new_ip(
                    AxisCombiner, (in_port, [d.width for d in drivers])
                )
                for i, driver in enumerate(drivers):
                    self._connect_axis(
                        source_port_for(driver), combiner.get_input_port(i)
                    )
                # Drive the sink from the combined (summed-width) output, going
                # through _connect_axis so the sink's converter_req is honoured
                # (a forced converter when the concatenated width differs, or
                # always for a field-checked sink).
                self._connect_axis(combiner.axi_out, in_port)

    def _want_converter(self, policy):
        """Whether to insert a width converter for a candidate (mismatched)
        connection, given the policy ('yes' | 'no' | 'random')."""
        if policy == "yes":
            return True
        if policy == "no":
            return False
        return random.random() < 0.5  # "random"

    def _connect_axis(self, source, sink):
        """Connect an AXIS ``source`` to a ``sink``, optionally routing through an
        AXI Stream data width converter. The sink's ``converter_req`` decides when
        a converter is mandatory (see ConverterReq); otherwise one is inserted on
        a width difference only when the configured policy asks for it. The policy
        is the I/O policy when either endpoint is an external port, otherwise the
        internal policy. An opportunistic converter is only feasible when the
        TDATA byte widths have an integer ratio (the Xilinx converter is a byte
        gearbox); otherwise the ports are connected directly."""
        is_io = isinstance(source, ExternalPort) or isinstance(sink, ExternalPort)
        policy = self._axis_io_conv if is_io else self._axis_internal_conv

        # A sink that ALWAYS requires a converter gets one even at matching widths:
        # the converter flattens any structured-TDATA field map (e.g. CORDIC's
        # xn_re/xn_im) into a plain stream the sink will accept.
        if sink.converter_req == ConverterReq.ALWAYS:
            self._insert_axis_converter(source, sink)
            return

        if source.width != sink.width:
            in_bytes = math.ceil(source.width / 8)
            out_bytes = math.ceil(sink.width / 8)
            lo, hi = sorted((in_bytes, out_bytes))
            ratio_ok = lo > 0 and hi % lo == 0
            # An ON_WIDTH_DIFF sink (e.g. an AXI DMA stream slave) hard-errors if a
            # mismatched width propagates onto it, so always insert a converter
            # there -- even when the byte ratio is non-integer (the Xilinx
            # converter may reject it; we want to observe that). For lenient sinks
            # the converter is optional (random policy) and only attempted when the
            # byte ratio is integer.
            if sink.converter_req == ConverterReq.ON_WIDTH_DIFF or (
                ratio_ok and self._want_converter(policy)
            ):
                self._insert_axis_converter(source, sink)
                return

        self._wire_axis(source, sink)

    def _insert_axis_converter(self, source, sink):
        """Insert an AXI Stream data width converter between ``source`` and
        ``sink`` and wire it up."""
        conv = self._new_ip(AxisDwidthConverter, (source.width, sink.width))
        self._wire_axis(source, conv.axi_in)
        self._wire_axis(conv.axi_out, sink)

    @staticmethod
    def _wire_axis(source, sink):
        """Make a single AXIS connection from ``source`` to ``sink``.

        ``sink.connect(source)`` works for every supported case: an IpPort sink
        delegates external sources correctly, and an ExternalPort sink accepts an
        IpPort source (source/sink are never both external)."""
        sink.connect(source)

    def _axi(self):
        """Create AXI ports"""
        masters = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == Protocol.AXI_MM
            and not p.connected
            and p.direction == Direction.OUTPUT
        ]
        slaves = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == Protocol.AXI_MM
            and not p.connected
            and p.direction == Direction.INPUT
        ]

        if not masters and not slaves:
            return

        logging.info("########## AXI ##########")

        # Incremental AXI not supported
        if self._axi_complete:
            assert False, "AXI processing called again"
        self._axi_complete = True

        self._bd_tcl += "\n########## AXI ##########\n"
        if not masters:
            # No internal AXI master: provide one per the configured strategy.
            choice = random.choice(self._axi_mm_no_master)
            logging.info(f"No AXI master; using '{choice}' no-master strategy")
            if choice == "jtag":
                # Pin-free JTAG-to-AXI master (no top-level AXI bus on the pins).
                # Its address space is mapped by the template's global
                # assign_bd_address (run before validate_bd_design).
                jtag = self._new_ip(JtagAxi)
                masters.append(jtag.master_port)
            elif choice == "external":
                # Top-level AXI master port (legacy behavior).
                master = self._create_external_port(
                    "axi_master",
                    Protocol.AXI_MM,
                    Direction.INPUT,
                    properties={"CONFIG.PROTOCOL": "AXI4LITE"},
                )
                masters.append(master)
            else:
                raise ValueError(
                    f"Unknown axi_mm.no_master option: {choice!r} "
                    "(expected 'external' or 'jtag')"
                )

        if not slaves:
            # If we don't have a slave, create a top-level slave
            slave = self._create_external_port(
                "axi_slave",
                Protocol.AXI_MM,
                Direction.OUTPUT,
                properties={"CONFIG.PROTOCOL": "AXI4LITE"},
            )
            slaves.append(slave)

        # TODO: Non-complete crossbars
        assert len(slaves)
        assert len(masters)

        # Decide if we will do single-level or two-level AXI
        two_level = len(slaves) > 16

        # Make sure we don't have too many slaves
        if two_level:
            assert len(slaves) <= 16 * 16, f"Too many AXI slaves: {len(slaves)}"
        else:
            assert len(slaves) <= 16, f"Too many AXI slaves: {len(slaves)}"

        if two_level:
            num_second_level = (len(slaves) + 15) // 16
            axi_first_level = self._new_ip(
                self._axi_class, (len(masters), num_second_level)
            )
            for i, master in enumerate(masters):
                master.connect(axi_first_level.port_masters[i])

            for i in range(num_second_level):
                num_this_level = min(16, len(slaves) - i * 16)
                axi_second_level = self._new_ip(self._axi_class, (1, num_this_level))

                # Connect first level to second level
                axi_first_level.port_slaves[i].connect(axi_second_level.port_masters[0])

                # Connect second level to slaves
                for j in range(num_this_level):
                    slave = slaves[i * 16 + j]
                    slave.connect(axi_second_level.port_slaves[j])
                    for master in masters:
                        pass
                        # self._assign_bd_addresses(master, slave)

        else:
            axi = self._new_ip(self._axi_class, (len(masters), len(slaves)))
            for i, master in enumerate(masters):
                master.connect(axi.port_masters[i])
            for i, slave in enumerate(slaves):
                slave.connect(axi.port_slaves[i])
                for master in masters:
                    # External masters don't have an address space?
                    pass
                    # self._assign_bd_addresses(master, slave)

    def _create_external_port(
        self, name, protocol, direction, width=None, properties=None
    ):
        assert isinstance(protocol, Protocol)
        assert isinstance(direction, Direction)

        port = ExternalPort(self, name, protocol, direction, width, properties)
        return port

    def _new_instance(self, ip_name, instance_name, properties=None):
        self._bd_tcl += f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        # Combine key, value pairs into a single string
        prop = ""
        for key, value in properties.items():
            prop += f"{key} {value} "
        self._bd_tcl += f'set_property -dict "{prop}" [get_bd_cells {instance_name}]\n'

    def _assign_bd_addresses(self, master_port, slave_port):
        for address_segment in slave_port.addr_segs:
            self._addr_space_tcl += f"assign_bd_address -target_address_space "

            if isinstance(master_port, ExternalPort):
                self._addr_space_tcl += f"{master_port.hier_name} "
            else:
                self._addr_space_tcl += (
                    f"/{master_port.ip.hier_name}/{master_port.addr_segs[0]} "
                )

            if slave_port.ip:
                self._addr_space_tcl += f"[get_bd_addr_segs {slave_port.ip.hier_name}/{address_segment}] -force\n"
            else:
                assert False  # JBG: Added this? I don't think this is reachable
                self._addr_space_tcl += (
                    f"[get_bd_addr_segs {slave_port.addr_seg_name}] -force\n"
                )

    def _new_ip(self, ip_class, args=None):
        """Create a new IP instance"""
        if args is None:
            args = []
        new_ip = ip_class(self, f"ip_{self._ip_idx}", *args)
        self.ip.append(new_ip)
        self._ip_idx += 1
        return new_ip
