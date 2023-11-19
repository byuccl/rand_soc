import random
import jinja2

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

            self._clocks()
            self._resets()
            self._external_io()
            # self._interrupts()

            self.out += "\n# Save the block design\n"
            self.out += f"save_bd_design\n"

            with open(output_path / "design.tcl", "w", encoding="utf-8") as f:
                f.write(self.out)

    def _clocks(self):
        all_clocks = []
        for ip in self.ip:
            for clk in ip.clk_inputs:
                all_clocks.append((ip, clk))

        # Create single external clock
        self.out += "\n########## Clocks ##########\n"
        self._create_port("I", "clk")

        for ip, clk in all_clocks:
            self._connect_port("clk", ip, clk)

    def _resets(self):
        all_resets = []
        for ip in self.ip:
            for reset in ip.reset_inputs:
                all_resets.append((ip, reset))

        # Create single external reset
        self.out += "\n########## Resets ##########\n"
        self._create_port("I", "reset")

        for ip, reset in all_resets:
            self._connect_port("reset", ip, reset)

    def _external_io(self):
        all_external_io = []
        for ip in self.ip:
            for io in ip.external_io_ports:
                all_external_io.append((ip, io))

        # Create external outputs
        self.out += "\n########## External I/O ##########\n"
        for ip, io in all_external_io:
            self._create_port(io.dir, f"{ip.hier_name}.{io.name}", width=io.width)
            self._connect_port(f"{ip.hier_name}.{io.name}", ip, io.name)

    def _create_port(self, direction, name, width=1):
        self.out += f"create_bd_port -dir {direction} -from {width-1} -to 0 {name}\n"

    def _connect_port(self, external_port, ip, name):
        self.out += f"connect_bd_net [get_bd_pins {external_port}] [get_bd_pins {ip.hier_name}/{name}]\n"
