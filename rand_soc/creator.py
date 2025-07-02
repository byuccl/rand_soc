import logging
import pathlib
import random
import sys
import yaml
import chevron

from .ip.reduce import Reduce
from .ip.slice_and_concat import SliceAndConcat
from .ip.accumulator import Accumulator
from .paths import ROOT_PATH
from .ip.axi import Axi
from .ip.axi_cdma import AxiCdma
from .ip.axi_hwicap import AxiHwicap
from .ip.axi_timer import AxiTimer
from .ip.axi_usb2_device import AxiUsb2Device
from .ip.clk_gen import ClkGen
from .ip.dft import Dft
from .ip.intc import Intc
from .ip.uartlite import Uartlite
from .ip.emc import Emc
from .ports import ExternalPort, ExternalPortInterface, ExternalPortRegular
from .ip.gpio import Gpio
from .ip.microblaze import Microblaze
from .ip.xadc_wiz import XadcWiz
from .ip.axi_can import AxiCan
from .ip.axi_ethernet_lite import AxiEthernetLite
from .ip.axi_iic import AxiIic
from .ip.axi_quad_spi import AxiQuadSpi


class DesignCreator:
    """Creates multiple designs"""

    def __init__(self):
        random.seed(0)

    def run(self, output_dir_path, num_designs):
        for i in range(num_designs):
            # Create design directory
            output_path = output_dir_path / f"design_{i}" / "design.tcl"

            design = RandomDesign()
            design.create()
            design.write(output_path)


class RandomDesign:
    """Creates a random design"""

    def __init__(self, output_dir_path, config_path=None, seed=None, part=None):
        if config_path is None:
            config_path = ROOT_PATH / "creator.yaml"
        if seed is not None:
            random.seed(seed)
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
        self._intc_complete = False
        self._output_dir_path = pathlib.Path(output_dir_path).resolve()

        # Enable logging
        log_file = self._output_dir_path / "log.txt"
        self._output_dir_path.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=log_file,
            filemode="w",
            format="%(asctime)s %(levelname)s: %(message)s",
            level=logging.DEBUG,
        )

    def write(self):
        output_file_path = self._output_dir_path / "design.tcl"
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(self.tcl_str)

        impl_constraints_tcl_path = self._output_dir_path / "impl_constraints.tcl"
        with open(impl_constraints_tcl_path, "w", encoding="utf-8") as f:
            f.write(self.impl_constraints_tcl)

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

        self._bd_tcl = ip_str + self._bd_tcl + self.ip_to_ip_connections_tcl + self._addr_space_tcl

        project_config["block_diagram"] = self._bd_tcl
        self.tcl_str = chevron.render(template, project_config)

        for ip in self.ip:
            self.impl_constraints_tcl += ip._impl_constraints_tcl

    def _ports(self):
        unhandled_ports = set()
        disconnected_ports_old = set()

        while True:
            if len(unhandled_ports) > 1000:
                logging.info("Too many unhandled ports - endless loop of port creation?")
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

            # AXI ports
            self._axi()

            # Data and control ports
            self._generic_ports(
                port_type="data",
                max_randomly_generated_inputs=128,
                max_randomly_generated_outputs=32,
            )
            self._generic_ports(
                port_type="control",
                max_randomly_generated_inputs=8,
                max_randomly_generated_outputs=8,
            )

        logging.info("")
        for port in unhandled_ports:
            logging.error("Unhandled port: %s", port)
        assert not unhandled_ports

    def _generic_ports(
        self, port_type, max_randomly_generated_inputs, max_randomly_generated_outputs
    ):
        """Connect data ports."""

        assert port_type in ("data", "control")

        if port_type in self.port_types_initialized:
            return
        self.port_types_initialized.add(port_type)

        logging.info(f"########## Connecting {port_type} ports ##########")
        self._bd_tcl += f"\n########## {port_type} ports ##########\n"
        out_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == port_type and not p.connected and p.direction == "O"
        ]
        in_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == port_type and not p.connected and p.direction == "I"
        ]
        num_in_pins = sum(p.width for p in in_ports)
        num_out_pins = sum(p.width for p in out_ports)

        # Create primary inputs for data (primary input is an output)
        #
        # At most max_randomly_generated_inputs will be created (unless num_in_pins is less than that,
        # in which case the maximum number of inputs will be num_in_pins)
        #
        # If there are no output pins, then at least one primary input will be created
        if port_type not in self._pi_ports:
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
                logging.info(f"Creating primary input port: {port_type}_I, width: {pi_width}")
                new_port = self._create_external_port(f"{port_type}_I", port_type, "I", pi_width)
                self._pi_ports[port_type] = new_port
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
            logging.info(f"Creating primary output port: {port_type}_O, width: {po_width}")
            new_port = self._create_external_port(f"{port_type}_O", port_type, "O", po_width)
            self._po_ports[port_type] = new_port

            if po_width < out_pins_needed:
                logging.info(f"Adding reducer from {out_pins_needed} to {po_width}")
                reducer = self._new_ip(Reduce, (port_type, out_pins_needed, po_width))
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

        self._random_port_connector(in_ports, out_ports)

    def _random_port_connector(self, in_ports, out_ports):
        if not in_ports and not out_ports:
            return

        logging.info(
            f"Will randomly connect {len(out_ports)} output ports to {len(in_ports)} input ports"
        )

        # Generate list of in and out ports, where each item is a tuple (port, index)
        # where index is the lowest bit number not connected
        in_ports_not_driven = [[port, 0] for port in in_ports]
        random.shuffle(in_ports_not_driven)

        out_ports_unused = [[port, 0] for port in out_ports]
        assert out_ports_unused

        # Connect all in ports
        next_out_port_idx = 0

        for in_port_and_pin_idx in in_ports_not_driven:
            drivers = []
            in_port = in_port_and_pin_idx[0]
            in_width = in_port.width
            in_width_unconnected = in_width
            logging.info(f"Connecting drivers of port {in_port.hier_name} [{in_width-1}:0]")

            num_connected = 0

            while in_width_unconnected:
                # Once we've used up all the output signals, this flag will switch to True
                # and we will randomly reuse output signals
                using_random_output = next_out_port_idx >= len(out_ports_unused)

                # Pick the output port
                if using_random_output:
                    out_port = random.choice(out_ports_unused)[0]
                    out_port_avail = None
                    # Randomly pick a pin range to use
                    out_width = min(out_port.width, in_width_unconnected)
                    out_bit_low = random.randint(0, out_port.width - out_width)
                    out_bit_high = out_bit_low + out_width - 1
                else:
                    out_port = out_ports_unused[next_out_port_idx][0]
                    # Identify unused pins from this port
                    out_port_avail = out_ports_unused[next_out_port_idx]
                    out_bit_high = out_port_avail[0].width - 1
                    out_bit_low = out_port_avail[1]

                out_width = out_bit_high - out_bit_low + 1

                if out_width == in_width_unconnected:
                    logging.info(
                        f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
                    )
                    drivers.append((out_port, out_bit_high, out_bit_low))
                    num_connected += out_width
                    next_out_port_idx += 1
                    in_width_unconnected = 0
                    break

                if out_width > in_width_unconnected:
                    logging.info(
                        f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_low + in_width_unconnected - 1}:{out_bit_low}]"
                    )
                    drivers.append((out_port, out_bit_low + in_width_unconnected - 1, out_bit_low))
                    num_connected += in_width_unconnected
                    if out_port_avail:
                        out_port_avail[1] += in_width_unconnected
                    in_width_unconnected = 0
                    break

                # out_width < in_width_unconnected
                logging.info(
                    f"  [{in_width_unconnected-1}:{in_width_unconnected-out_width}] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
                )
                drivers.append((out_port, out_bit_high, out_bit_low))
                num_connected += out_width
                next_out_port_idx += 1
                in_width_unconnected -= out_width

            assert (
                num_connected == in_width
            ), f"num_connected: {num_connected}, in_width: {in_width}"

            # Connect all drivers to the in port
            self._connect_multiple_drivers_to_port(in_port, drivers)

    def _connect_multiple_drivers_to_port(self, port, drivers):
        """Connect multiple drivers to a port"""
        self._new_ip(
            SliceAndConcat,
            (port, drivers),
        )

    def _clocks(self):
        clock_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "clk" and not p.connected and p.direction == "I"
        ]

        # Create single external clock
        logging.info("########## Clocks ##########")
        self._bd_tcl += "\n########## Clocks ##########\n"
        if "clock" not in self._pi_ports:
            clk_ip = self._new_ip(ClkGen)
            logging.info("Creating external clock port: clock")
            self._create_external_port("clk", "clk", "I", width=1).connect(clk_ip.port_clk_in)
            self._pi_ports["clock"] = clk_ip.port_clk_out

        logging.info(f"Connecting {clock_inputs} to clock")
        self._pi_ports["clock"].connect(clock_inputs)

    def _resets(self):
        logging.info("########## Resets ##########")
        # Collect unconnected reset inputs
        reset_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "reset" and not p.connected and p.direction == "I"
        ]

        # Create single external reset
        if "reset" not in self._pi_ports:
            self._bd_tcl += "\n########## Resets ##########\n"
            logging.info("Creating external reset port: reset")
            self._pi_ports["reset"] = self._create_external_port("reset", "reset", "I", 1)

        logging.info(f"Connecting {reset_inputs} to reset")
        self._pi_ports["reset"].connect(reset_inputs)

    def _interrupts(
        self,
    ):
        interrupt_outputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "irq" and not p.connected and p.direction == "O"
        ]
        interrupt_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "xilinx.com:interface:mbinterrupt_rtl:1.0"
            and not p.connected
            and p.direction == "Slave"
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
                "irq", "xilinx.com:interface:mbinterrupt_rtl:1.0", "Master"
            )
            interrupt_inputs.append(irq_out)

        self._bd_tcl += "\n########## Interrupts ##########\n"
        for interrupt_input in interrupt_inputs:
            intc = self._new_ip(Intc, (len(interrupt_outputs),))
            for i, interrupt_output in enumerate(interrupt_outputs):
                intc.input_ports[i].connect(interrupt_output)
            interrupt_input.connect(intc.port_irq)

    def _external_interfaces(self):
        ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol
            in (
                # GPIO general purpose I/O and 3-state pins
                "xilinx.com:interface:gpio_rtl:1.0",
                # UART master interface
                "xilinx.com:interface:uart_rtl:1.0",
                # EMC_INTF port
                "xilinx.com:interface:emc_rtl:1.0",
                # axi_usb2_device ULPI port, for use with USB PHY
                "xilinx.com:interface:ulpi_rtl:1.0",
                # axi_hwicap ICAP and arbiter ports, read/write to FPGA configuration memory
                "xilinx.com:interface:icap_rtl:1.0",
                "xilinx.com:interface:arb_rtl:1.0",
                # XADC input port
                "xilinx.com:interface:diff_analog_io_rtl:1.0",
                # CAN
                "xilinx.com:interface:can_rtl:1.0",
                # IIC
                "xilinx.com:interface:iic_rtl:1.0",
                # EthernetLite
                "xilinx.com:interface:mii_rtl:1.0",
                "xilinx.com:interface:mdio_rtl:1.0",
                # Quad SPI
                "xilinx.com:interface:spi_rtl:1.0",
                "xilinx.com:display_startup_io:startup_io_rtl:1.0",
                "xilinx.com:interface:startup_rtl:1.0",
            )
            and not p.connected
        ]

        # Create external outputs
        self._bd_tcl += "\n########## GPIO, UART ##########\n"
        for port in ports:
            self._create_external_port(
                f"{port.ip.hier_name}_{port.name}", port.protocol, port.direction
            ).connect(port)

    def _axi(self):
        """Create AXI ports"""
        masters = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "xilinx.com:interface:aximm_rtl:1.0"
            and not p.connected
            and p.direction == "Master"
        ]
        slaves = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "xilinx.com:interface:aximm_rtl:1.0"
            and not p.connected
            and p.direction == "Slave"
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
                "xilinx.com:interface:aximm_rtl:1.0",
                "Slave",
                properties={"CONFIG.PROTOCOL": "AXI4LITE"},
            )
            masters.append(master)

        if not slaves:
            # If we don't have a slave, create a top-level slave
            slave = self._create_external_port(
                "axi_slave",
                "xilinx.com:interface:aximm_rtl:1.0",
                "Master",
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

    def _create_external_port(self, name, protocol, direction, width=None, properties=None):
        if protocol.startswith("xilinx.com:"):
            assert width is None
            port = ExternalPortInterface(self, name, protocol, direction, properties)
        else:
            port = ExternalPortRegular(self, name, protocol, direction, width)
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
                self._addr_space_tcl += f"/{master_port.ip.hier_name}/{master_port.addr_segs[0]} "

            if slave_port.ip:
                self._addr_space_tcl += (
                    f"[get_bd_addr_segs {slave_port.ip.hier_name}/{address_segment}] -force\n"
                )
            else:
                assert False  # JBG: Added this? I don't think this is reachable
                self._addr_space_tcl += f"[get_bd_addr_segs {slave_port.addr_seg_name}] -force\n"

    def _new_ip(self, ip_class, args=None):
        """Create a new IP instance"""
        if args is None:
            args = []
        new_ip = ip_class(self, f"ip_{self._ip_idx}", *args)
        self.ip.append(new_ip)
        self._ip_idx += 1
        return new_ip
