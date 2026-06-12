from collections import defaultdict
import logging
import pathlib
import random
import sys
import yaml
import chevron

from .ip.axis_broadcaster import AxisBroadcaster
from .port_assigner import port_assigner_axis, port_assigner_random
from .typedefs import Direction, NetType, Protocol
from .ip.reset import SystemReset
from .ip.reduce import Reduce
from .ip.slice_and_concat import SliceAndConcat
from .paths import ROOT_PATH
from .ports import ExternalPort

# Manually added IP
from .ip.axi import Axi
from .ip.clk_gen import ClkGen
from .ip.intc import Intc

# Randomly added IP
# pylint: disable=unused-import
from .ip.accumulator import Accumulator
from .ip.axi_cdma import AxiCdma
from .ip.axi_hwicap import AxiHwicap
from .ip.axi_timer import AxiTimer
from .ip.axi_usb2_device import AxiUsb2Device
from .ip.dft import Dft
from .ip.uartlite import Uartlite
from .ip.emc import Emc
from .ip.gpio import Gpio
from .ip.microblaze import Microblaze
from .ip.xadc_wiz import XadcWiz
from .ip.axi_can import AxiCan
from .ip.axi_ethernet_lite import AxiEthernetLite
from .ip.axi_iic import AxiIic
from .ip.axi_quad_spi import AxiQuadSpi
from .ip.fft import Fft

# pylint: enable=unused-import


class RandomDesign:
    """Creates a random design"""

    def __init__(self, output_dir_path, config_path=None, seed=None, part=None):
        if config_path is None:
            config_path = ROOT_PATH / "creator.yaml"

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
        }

        # env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        template_path = ROOT_PATH / "run.tcl.mustache"
        assert template_path.is_file(), f"Template file {template_path} does not exist"
        with open(template_path, "r") as f:
            template = f.read()

        creator_yaml = self.get_creator_yaml()
        min_ip = creator_yaml["min_ip"]
        max_ip = creator_yaml["max_ip"]
        ip_list = self.get_yaml_available_ip(creator_yaml)

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
            for _ in range(8):
                primary_sources.append(
                    self._create_external_port(
                        f"external_axis_source_{_}",
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
        """Build AXI Stream connections"""
        fanout_degree = defaultdict(int)
        fanout_next_idx = defaultdict(int)

        driver_map_with_fanout_idx = {}
        broadcasters = {}

        # First determine fanout for each driver
        for in_port, drivers in driver_map.items():
            for driver in drivers:
                fanout_degree[driver] += 1

        # Now assign fanout index to each driver
        for in_port, drivers in driver_map.items():
            driver_list = []
            for driver in drivers:
                fanout_idx = None
                if fanout_degree[driver] > 1:
                    fanout_idx = fanout_next_idx[driver]
                    fanout_next_idx[driver] += 1
                driver_list.append((driver, fanout_idx))
            driver_map_with_fanout_idx[in_port] = driver_list

        # Now create the AXI Stream broadcasters as needed
        for port, degree in fanout_degree.items():
            if degree > 1:
                # raise NotImplementedError("AXI Stream broadcasters not yet tested")
                broadcasters[port] = self._new_ip(AxisBroadcaster, (port, degree))

        for in_port, drivers in driver_map_with_fanout_idx.items():

            # in_port.connected = True
            # for driver, fanout_idx in drivers:
            #     driver.connected = True

            assert len(drivers) == 1
            driver = drivers[0][0]
            broadcast_idx = drivers[0][1]

            if broadcast_idx is None:
                in_port.connect(driver)
            else:
                in_port.connect(broadcasters[driver].get_output_port(broadcast_idx))

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
            print("AXI processing called again")
            print("Masters:")
            for master in masters:
                print(master)
            print("Slaves:")
            for slave in slaves:
                print(slave)
            assert False
        self._axi_complete = True

        self._bd_tcl += "\n########## AXI ##########\n"
        if not masters:
            # If we don't have a master, create a top-level master
            master = self._create_external_port(
                "axi_master",
                Protocol.AXI_MM,
                Direction.INPUT,
                properties={"CONFIG.PROTOCOL": "AXI4LITE"},
            )
            masters.append(master)

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
            axi_first_level = self._new_ip(Axi, (len(masters), num_second_level))
            for i, master in enumerate(masters):
                master.connect(axi_first_level.port_masters[i])

            for i in range(num_second_level):
                num_this_level = min(16, len(slaves) - i * 16)
                axi_second_level = self._new_ip(Axi, (1, num_this_level))

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
            axi = self._new_ip(Axi, (len(masters), len(slaves)))
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
