import random
from .ip import IP


class Gpio(IP):
    # def __init__(self, name):
    #     super().__init__()
    #     self.hier_name = name

    @property
    def name(self):
        return "gpio"

    def randomize(self):
        self.width1 = random.randint(1, 32)
        if random.choice([True, False]):
            self.width2 = random.randint(1, 32)
        else:
            self.width2 = None

        # Todo:
        # All inputs
        # All outputs
        # Default output value
        # Default tri-state value
        # Interrupt

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        gpio_name = "gpio_0"
        self.new_instance("xilinx.com:ip:axi_gpio:2.0", gpio_name)
        self.external_outputs

        self.instance_str += "# Create BD pins\n"
        self.create_hier_pin("I", "clk")
        self.create_hier_pin("I", "reset")
        self.create_hier_pin("O", "gpio1", self.width1)
        self.external_outputs.append(("gpio1", self.width1))
        if self.width2:
            self.create_hier_pin("O", "gpio2", self.width2)
            self.external_outputs.append(("gpio2", self.width2))
        self.connect_bd_pin("clk", f"{gpio_name}/s_axi_aclk")
        self.connect_bd_pin("reset", f"{gpio_name}/s_axi_aresetn")
        self.connect_bd_pin("gpio", f"{gpio_name}/GPIO")
