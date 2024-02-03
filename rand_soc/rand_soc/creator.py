import logging
import pathlib
import random
import sys

import chevron

from .ip.slice_and_concat import SliceAndConcat
from .ip.accumulator import Accumulator
from .paths import ROOT_PATH
from .ip.axi import Axi
from .ip.clk_gen import ClkGen
from .ip.intc import Intc
from .ip.uartlite import Uartlite
from .ports import ExternalPortInterface, ExternalPortRegular, Port
from .ip.gpio import Gpio
from .ip.microblaze import Microblaze


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

    def __init__(self, output_dir_path, seed=None):
        if seed is not None:
            random.seed(seed)

        self.tcl_str = ""

        # Block diagram string
        self._bd_tcl = ""
        self.ip_to_ip_connections_tcl = "\n########## IP to IP connections ##########\n"
        self._addr_space_tcl = "\n########## Address space ##########\n"
        self.ip = []
        self._port_clock = None
        self._port_reset = None
        self._pi_port = None
        self._pi_port_control = None
        self._po_port = None
        self.data_ports_initialized = False
        self.control_ports_initialized = False
        self._ip_idx = 0
        self._axi_complete = False
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

    def create(self):
        """Create the design tcl"""
        project_config = {
            "part": "xc7a200tsbg484-1",
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
        with open(template_path) as f:
            template = f.read()

        ip_available = [Gpio, Microblaze, Uartlite, Accumulator]
        for ip in ip_available:
            num_ip = random.randint(1, 3)
            for _ in range(num_ip):
                self._new_ip(ip)

        for ip in self.ip:
            ip.randomize()

        for ip in self.ip:
            ip.instance()

        self._ports()

        ip_str = "".join([ip.bd_str for ip in self.ip])

        self._bd_tcl = ip_str + self._bd_tcl + self.ip_to_ip_connections_tcl + self._addr_space_tcl

        project_config["block_diagram"] = self._bd_tcl
        self.tcl_str = chevron.render(template, project_config)

    def _ports(self):
        unhandled_ports = set()
        disconnected_ports_old = set()

        while True:
            if len(unhandled_ports) > 10000:
                print("Too many unhandled ports - endless loop of port creation?")
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

            # GPIO, UART ports
            self._gpio()

            # Interrupt ports
            self._interrupts()

            # AXI ports
            self._axi()

            # Data and control ports
            self._data_ports()
            self._control_ports()

        for port in unhandled_ports:
            print("Unhandled port:", port)

    def _control_ports(self):
        if self.control_ports_initialized:
            return
        self.control_ports_initialized = True

        self._bd_tcl += "\n########## Control ports ##########\n"
        """Connect control ports."""
        out_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "control" and not p.connected and p.direction == "O"
        ]
        in_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "control" and not p.connected and p.direction == "I"
        ]
        num_in_pins = sum([p.width for p in in_ports])
        num_out_pins = sum([p.width for p in out_ports])
        print(f"Num input pins: {num_in_pins}")
        print(f"Num output pins: {num_out_pins}")

        # Create primary inputs for control
        # max is lesser of 8 and the number of input pins
        if self._pi_port_control is None:
            min_pis = 0
            if num_out_pins == 0 and num_in_pins > 0:
                min_pis = 1
            pi_width = random.randint(min_pis, min(8, num_in_pins))
            if pi_width:
                self._pi_port_control = self._create_external_port(
                    "control_I", "control", "I", pi_width
                )
                out_ports.insert(0, self._pi_port_control)

        self._random_port_connector(in_ports, out_ports)

    def _data_ports(self):
        if self.data_ports_initialized:
            return
        self.data_ports_initialized = True

        self._bd_tcl += "\n########## Data ports ##########\n"
        """Connect data ports."""
        out_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "data" and not p.connected and p.direction == "O"
        ]
        in_ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "data" and not p.connected and p.direction == "I"
        ]
        num_in_pins = sum([p.width for p in in_ports])
        num_out_pins = sum([p.width for p in out_ports])
        print(f"Num input pins: {num_in_pins}")
        print(f"Num output pins: {num_out_pins}")

        # Create primary inputs for data
        # max is lesser of 128 and the number of input pins
        if self._pi_port is None:
            min_pis = 0
            if num_out_pins == 0 and num_in_pins > 0:
                min_pis = 1
            pi_width = random.randint(min_pis, min(128, num_in_pins))
            if pi_width:
                self._pi_port = self._create_external_port("data_I", "data", "I", pi_width)
                out_ports.insert(0, self._pi_port)

        # # Create primary outputs for data
        # # max is lesser of 128 and the number of output pins
        # if self._po_port is None:
        #     po_width = random.randint(0, min(128, num_out_pins))
        #     self._po_port = self._create_external_port("data_O", "data", "O", po_width)
        #     in_ports.append(self._po_port)

        self._random_port_connector(in_ports, out_ports)

    def _random_port_connector(self, in_ports, out_ports):
        print(f"Conecting {len(out_ports)} output ports to {len(in_ports)} input ports")
        # Generate list of in and out ports, where each item is a tuple (port, index)
        # where index is the lowest bit number not connected
        in_ports_not_driven = [[port, 0] for port in in_ports]
        random.shuffle(in_ports_not_driven)

        out_ports_unused = [[port, 0] for port in out_ports]
        # random.shuffle(out_ports_unused)

        # Connect all in ports
        next_out_port_idx = 0
        for i in range(len(in_ports_not_driven)):
            drivers = []
            in_port = in_ports_not_driven[i][0]
            in_width = in_port.width
            in_width_unconnected = in_width
            print(f"Connecting drivers of port {in_port.hier_name}, width {in_width}")

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
                    print(
                        f"  Driving by exact width port {out_port.hier_name}, {out_bit_high} downto {out_bit_low}"
                    )
                    drivers.append((out_port, out_bit_high, out_bit_low))
                    num_connected += out_width
                    next_out_port_idx += 1
                    in_width_unconnected = 0
                    break
                elif out_width > in_width_unconnected:
                    print(
                        f"  Driving by wider port {out_port.hier_name}, {out_bit_low + in_width - 1} downto {out_bit_low}"
                    )
                    drivers.append((out_port, out_bit_low + in_width - 1, out_bit_low))
                    num_connected += in_width_unconnected
                    if out_port_avail:
                        out_port_avail[1] += in_width_unconnected
                    in_width_unconnected = 0
                    break
                else:
                    print(
                        f"  Driving by narrower port {out_port.hier_name}, {out_bit_high} downto {out_bit_low}"
                    )
                    drivers.append((out_port, out_bit_high, out_bit_low))
                    num_connected += out_width
                    next_out_port_idx += 1
                    in_width_unconnected -= out_width
                    # print(f"New in_width: {in_width}")

            assert (
                num_connected == in_width
            ), f"num_connected: {num_connected}, in_width: {in_width}"

            # Connect all drivers to the in port
            self._connect_multiple_drivers_to_port(in_port, drivers)

        # in_ports_not_driven = in_ports_not_driven[i:]
        # print(in_ports_not_driven)
        assert not in_ports_not_driven

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
        self._bd_tcl += "\n########## Clocks ##########\n"
        if self._port_clock is None:
            clk_ip = self._new_ip(ClkGen)
            self._create_external_port("clk", "clk", "I", width=1).connect(clk_ip.port_clk_in)
            self._port_clock = clk_ip.port_clk_out

        self._port_clock.connect(clock_inputs)

    def _resets(self):
        # Collect unconnected reset inputs
        reset_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "reset" and not p.connected and p.direction == "I"
        ]

        # Create single external reset
        if self._port_reset is None:
            self._bd_tcl += "\n########## Resets ##########\n"
            self._port_reset = self._create_external_port("reset", "reset", "I", 1)

        self._port_reset.connect(reset_inputs)

    def _interrupts(
        self,
    ):
        interrupt_outputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "irq" and not p.connected and p.direction == "O"
        ]
        interrupt_microblaze_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "xilinx.com:interface:mbinterrupt_rtl:1.0"
            and not p.connected
            and p.direction == "Slave"
        ]

        self._bd_tcl += "\n########## Interrupts ##########\n"
        for interrupt_input in interrupt_microblaze_inputs:
            intc = self._new_ip(Intc, (len(interrupt_outputs),))
            for i, interrupt_output in enumerate(interrupt_outputs):
                intc.input_ports[i].connect(interrupt_output)
            interrupt_input.connect(intc.port_irq)

    def _gpio(self):
        ports = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol
            in (
                "xilinx.com:interface:gpio_rtl:1.0",
                "xilinx.com:interface:uart_rtl:1.0",
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
        if not masters or not slaves:
            return

        # Incremental AXI not supported
        assert not self._axi_complete
        self._axi_complete = True

        # TODO: Non-complete crossbars
        assert len(slaves)
        assert len(masters)

        self._bd_tcl += "\n########## AXI ##########\n"
        axi = self._new_ip(Axi, (len(masters), len(slaves)))

        for i, master in enumerate(masters):
            master.connect(axi.port_masters[i])
        for i, slave in enumerate(slaves):
            slave.connect(axi.port_slaves[i])
            for master in masters:
                self._assign_bd_address(master, slave)

    def _create_external_port(self, name, protocol, direction, width=None):
        if protocol.startswith("xilinx.com:interface:"):
            port = ExternalPortInterface(self, name, protocol, direction)
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

    def _assign_bd_address(self, master_port, slave_port):
        self._addr_space_tcl += f"assign_bd_address -target_address_space /{master_port.ip.hier_name}/{master_port.addr_seg_name} "
        if slave_port.ip:
            self._addr_space_tcl += (
                f"[get_bd_addr_segs {slave_port.ip.hier_name}/{slave_port.addr_seg_name}] -force\n"
            )
        else:
            self._addr_space_tcl += f"[get_bd_addr_segs {slave_port.addr_seg_name}] -force\n"

    def _new_ip(self, ip_class, args=None):
        """Create a new IP instance"""
        if args is None:
            args = []
        new_ip = ip_class(self, f"ip_{self._ip_idx}", *args)
        self.ip.append(new_ip)
        self._ip_idx += 1
        return new_ip
