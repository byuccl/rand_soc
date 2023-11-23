import random
import sys

import jinja2

from .axi import Axi
from .clk_gen import ClkGen
from .intc import Intc
from .uartlite import Uartlite
from .ports import ExternalPortInterface, ExternalPortRegular, Port
from .gpio import Gpio
from .microblaze import Microblaze


class DesignCreator:
    """Creates multiple designs"""

    def __init__(self):
        random.seed(0)

    def run(self, output_dir_path, num_designs):
        for i in range(num_designs):
            # Create design directory
            output_path = output_dir_path / f"design_{i}"
            output_path.mkdir(parents=True, exist_ok=True)

            design = RandomDesign()
            design.create()
            with open(output_path / "design.tcl", "w", encoding="utf-8") as f:
                f.write(design.tcl_str)


class RandomDesign:
    """Creates a random design"""

    def __init__(self):
        self.tcl_str = ""

        # Block diagram string
        self._bd_tcl = ""
        self.ip_to_ip_connections_tcl = "\n########## IP to IP connections ##########\n"
        self._addr_space_tcl = "\n########## Address space ##########\n"
        self.ip = []
        self.port_clock = None
        self.port_reset = None
        self.ip_idx = 0
        self.axi_complete = False

    def create(self):
        """Create the design tcl"""
        project_config = {"part": "xc7a200tsbg484-1", "bd_name": "design_1"}

        env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        template = env.get_template("run.tcl.j2")

        ip_available = [Gpio, Microblaze, Uartlite]
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

        self._bd_tcl = (
            ip_str + self._bd_tcl + self.ip_to_ip_connections_tcl + self._addr_space_tcl
        )

        project_config["block_diagram"] = self._bd_tcl
        self.tcl_str = template.render(project_config)

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

        for port in unhandled_ports:
            print("Unhandled port:", port)

    def _clocks(self):
        clock_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "clk" and not p.connected and p.direction == "I"
        ]

        # Create single external clock
        self._bd_tcl += "\n########## Clocks ##########\n"
        if self.port_clock is None:
            clk_ip = self._new_ip(ClkGen)
            self._create_external_port("clk", "clk", "I", width=1).connect(
                clk_ip.port_clk_in
            )
            self.port_clock = clk_ip.port_clk_out

        self.port_clock.connect(clock_inputs)

    def _resets(self):
        # Collect unconnected reset inputs
        reset_inputs = [
            p
            for ip in self.ip
            for p in ip.ports
            if p.protocol == "reset" and not p.connected and p.direction == "I"
        ]

        # Create single external reset
        if self.port_reset is None:
            self._bd_tcl += "\n########## Resets ##########\n"
            self.port_reset = self._create_external_port("reset", "reset", "I", 1)

        self.port_reset.connect(reset_inputs)

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
        assert not self.axi_complete
        self.axi_complete = True

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
            self._addr_space_tcl += f"[get_bd_addr_segs {slave_port.ip.hier_name}/{slave_port.addr_seg_name}] -force\n"
        else:
            self._addr_space_tcl += (
                f"[get_bd_addr_segs {slave_port.addr_seg_name}] -force\n"
            )

    def _new_ip(self, ip_class, args=None):
        """Create a new IP instance"""
        if args is None:
            args = []
        new_ip = ip_class(self, f"ip_{self.ip_idx}", *args)
        self.ip.append(new_ip)
        self.ip_idx += 1
        return new_ip
