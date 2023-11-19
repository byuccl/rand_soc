import random

from .ports import ExternalPort
from .ip import IP
from .utils import all_ones, randbool, randintwidth


class Gpio(IP):
    @property
    def name(self):
        return "gpio"

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        gpio_name = "gpio_0"
        config = {}

        # I/O
        if self.config_dir == "I":
            config["CONFIG.C_ALL_INPUTS"] = 1
        elif self.config_dir == "O":
            config["CONFIG.C_ALL_OUTPUTS"] = 1
        elif self.config_dir == "IO":
            config["CONFIG.C_TRI_DEFAULT"] = hex(self.config_default_tristate_val)

        if self.config_dir in ("I", "IO"):
            self.create_hier_pin("I", "gpio_i", self.config_width)
            self.external_io_ports.append(
                ExternalPort("gpio_i", "I", self.config_width)
            )

        if self.config_dir in ("O", "IO"):
            self.create_hier_pin("O", "gpio_o", self.config_width)
            self.external_io_ports.append(
                ExternalPort("gpio_o", "O", self.config_width)
            )
            config["CONFIG.C_DOUT_DEFAULT"] = hex(self.config_default_out_val)

        if self.config_dual_channel:
            config["CONFIG.C_IS_DUAL"] = 1
            if self.config_dir2 == "I":
                config["CONFIG.C_ALL_INPUTS_2"] = 1
            elif self.config_dir2 == "O":
                config["CONFIG.C_ALL_OUTPUTS_2"] = 1
            elif self.config_dir2 == "IO":
                config["CONFIG.C_TRI_DEFAULT_2"] = hex(
                    self.config_default_tristate_val2
                )

            if self.config_dir2 in ("I", "IO"):
                self.create_hier_pin("I", "gpio_2_i", self.width2)
                self.external_io_ports.append(
                    ExternalPort("gpio_2_i", "I", self.width2)
                )

            if self.config_dir2 in ("O", "IO"):
                self.create_hier_pin("O", "gpio_2_o", self.width2)
                self.external_io_ports.append(
                    ExternalPort("gpio_2_o", "O", self.width2)
                )
                config["CONFIG.C_DOUT_DEFAULT_2"] = hex(self.config_default_out_val2)

        self.new_instance("xilinx.com:ip:axi_gpio:2.0", gpio_name, config)

        self.instance_str += "# Create BD pins\n"
        self.create_hier_pin("I", "clk")
        self.create_hier_pin("I", "reset")

        self.connect_bd_pin("clk", f"{gpio_name}/s_axi_aclk")
        self.connect_bd_pin("reset", f"{gpio_name}/s_axi_aresetn")
        self.connect_bd_pin("gpio", f"{gpio_name}/GPIO")

    def randomize(self):
        self.config_dir = "IO"  # random.choice(["I", "O", "IO"])
        self.config_width = random.randint(1, 32)
        if self.config_dir in ("O", "IO"):
            self.config_default_out_val = random.choice(
                (0, all_ones(self.config_width), randintwidth(self.config_width))
            )
        if self.config_dir in ("IO",):
            self.config_default_tristate_val = random.choice(
                (0, all_ones(self.config_width), randintwidth(self.config_width))
            )

        self.config_dual_channel = randbool()
        if self.config_dual_channel:
            self.config_dir2 = random.choice(["I", "O", "IO"])
            self.width2 = random.randint(1, 32)
            if self.config_dir2 in ("O", "IO"):
                self.config_default_out_val2 = random.choice(
                    (0, all_ones(self.width2), randintwidth(self.width2))
                )
            if self.config_dir2 in ("IO",):
                self.config_default_tristate_val2 = random.choice(
                    (0, all_ones(self.width2), randintwidth(self.width2))
                )

        # TODO: GPIO Interrupt
