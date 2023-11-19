import random

import jinja2

from .ports import Port
from .utils import pull_from_list
from .gpio import Gpio
from .microblaze import Microblaze


class DesignCreator:
    def __init__(self):
        random.seed(0)

    def run(self, output_dir_path, num_designs):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        project_config = {"part": "xc7a200tsbg484-1", "bd_name": "design_1"}

        template = env.get_template("run.tcl.j2")

        for i in range(num_designs):
            # Create design directory
            output_path = output_dir_path / f"design_{i}"
            output_path.mkdir(parents=True, exist_ok=True)

            self.out = template.render(project_config)

            microblaze = Microblaze("ip_0")
            gpio = Gpio("ip_1")
            self.ip = [microblaze, gpio]

            for ip in self.ip:
                ip.randomize()

            for ip in self.ip:
                ip.instance()

            for ip in self.ip:
                self.out += ip.instance_str

            self._ports()
            # self._interrupts()

            self.out += "\n# Save the block design\n"
            self.out += f"save_bd_design\n"

            with open(output_path / "design.tcl", "w", encoding="utf-8") as f:
                f.write(self.out)

    def _ports(self):
        all_ports = [port for ip in self.ip for port in ip.ports]

        # Clock ports
        clock_ports = []
        pull_from_list(all_ports, clock_ports, lambda p: p.protocol == "clk")
        self._clocks(clock_ports)

        # Reset ports
        reset_ports = []
        pull_from_list(all_ports, reset_ports, lambda p: p.protocol == "reset")
        self._resets(reset_ports)

        # GPIO ports
        gpio_ports = []
        pull_from_list(
            all_ports,
            gpio_ports,
            lambda p: p.protocol == "xilinx.com:interface:gpio_rtl:1.0",
        )
        self._gpio(gpio_ports)

        for port in all_ports:
            print("Unhandled port:", port)
        if all_ports:
            raise Exception("Unhandled ports")

    def _clocks(self, clock_ports):
        # Create single external clock
        self.out += "\n########## Clocks ##########\n"
        self._create_external_port(
            Port(None, "clk", "I", width=1, protocol="clk"), clock_ports
        )

    def _resets(self, reset_ports):
        # Create single external reset
        self.out += "\n########## Resets ##########\n"
        self._create_external_port(
            Port(None, "reset", "I", width=1, protocol="reset"), reset_ports
        )

    def _gpio(self, ports):
        # Create external outputs
        self.out += "\n########## GPIO ##########\n"
        for port in ports:
            self._create_external_port(
                Port(
                    None,
                    f"{port.ip.hier_name}_{port.name}",
                    port.dir,
                    port.width,
                    port.protocol,
                    port.mode,
                ),
                (port,),
            )

    def _create_external_port(self, port, connect_to_ports=None):
        assert isinstance(port, Port)
        if port.protocol.startswith("xilinx.com:interface:"):
            self.out += f"create_bd_intf_port -mode {port.mode} -vlnv {port.protocol} {port.name}\n"
        else:
            self.out += f"create_bd_port -dir {port.dir} -from {port.width-1} -to 0 {port.name}\n"
        if connect_to_ports:
            for port_to in connect_to_ports:
                self._connect_port(port, port_to)

    def _connect_port(self, port1, port2):
        assert isinstance(port1, Port)
        assert isinstance(port2, Port)
        if port1.protocol.startswith("xilinx.com:interface:"):
            self.out += f"connect_bd_intf_net [get_bd_intf_pins {port1.name}] [get_bd_intf_pins {port2.hier_name}]\n"
        else:
            self.out += f"connect_bd_net [get_bd_pins {port1.name}] [get_bd_pins {port2.hier_name}]\n"
