import jinja2

from .microblaze import Microblaze


class DesignCreator:
    def __init__(self):
        self.out = ""

    def run(self):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        project_config = {"part": "xc7a200tsbg484-1", "bd_name": "design_1"}

        template = env.get_template("run.tcl.j2")

        self.out += template.render(project_config)

        microblaze = Microblaze("ip_0")
        self.ip = [microblaze]

        for module in self.ip:
            module.instance()

        for module in self.ip:
            self.out += module.instance_str

        self._clocks()
        self._resets()
        self._interrupts()

        self.out += "\n# Save the block design\n"
        self.out += f"save_bd_design\n"

        self.project_tcl_str = self.out

    def _clocks(self):
        all_clocks = []
        for ip in self.ip:
            for clk in ip.clk_inputs:
                all_clocks.append((ip, clk))

        # Create single external clock
        self.out += "\n########## Clocks ##########\n"
        self.create_port("I", "clk")

        for ip, clk in all_clocks:
            self.connect_port("clk", ip, clk)

    def _resets(self):
        all_resets = []
        for ip in self.ip:
            for reset in ip.reset_inputs:
                all_resets.append((ip, reset))

        # Create single external reset
        self.out += "\n########## Resets ##########\n"
        self.create_port("I", "reset")

        for ip, reset in all_resets:
            self.connect_port("reset", ip, reset)

    def create_port(self, direction, name):
        self.out += f"create_bd_port -dir {direction} {name}\n"

    def connect_port(self, external_port, ip, pin_name):
        self.out += f"connect_bd_net [get_bd_pins {external_port}] [get_bd_pins {ip.hier_name}/{pin_name}]\n"
