import random

from .ports import Port
from .ip import IP
from .utils import all_ones, randbool, randintwidth


class Gpio(IP):
    def __init__(self, name):
        super().__init__(name)
        self.config_dir = None
        self.config_width = None
        self.config_default_out_val = None
        self.config_default_tristate_val = None
        self.config_dual_channel = None
        self.config_dir2 = None
        self.config_width2 = None
        self.config_default_out_val2 = None
        self.config_default_tristate_val2 = None

    @property
    def name(self):
        return "gpio"

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        gpio_name = "gpio_0"
        config = {}

        if self.config_dir == "I":
            config["CONFIG.C_ALL_INPUTS"] = 1
        elif self.config_dir == "O":
            config["CONFIG.C_ALL_OUTPUTS"] = 1
        elif self.config_dir == "IO":
            config["CONFIG.C_TRI_DEFAULT"] = hex(self.config_default_tristate_val)

        if self.config_dir in ("O", "IO"):
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

            if self.config_dir2 in ("O", "IO"):
                config["CONFIG.C_DOUT_DEFAULT_2"] = hex(self.config_default_out_val2)

        self._new_instance("xilinx.com:ip:axi_gpio:2.0", gpio_name, config)

        self._create_hier_pin(
            Port(
                "GPIO",
                self.config_dir,
                self.config_width,
                "xilinx.com:interface:gpio_rtl:1.0",
                mode="Master",
                ip=self,
            ),
            (f"{gpio_name}/GPIO",),
        )
        if self.config_dual_channel:
            self._create_hier_pin(
                Port(
                    "GPIO2",
                    self.config_dir2,
                    self.config_width2,
                    "xilinx.com:interface:gpio_rtl:1.0",
                    mode="Master",
                    ip=self,
                ),
                (f"{gpio_name}/GPIO2",),
            )

        self.instance_str += "# Create BD pins\n"
        self._create_hier_pin(
            Port("clk", "I", 1, "clk", ip=self), (f"{gpio_name}/s_axi_aclk",)
        )
        self._create_hier_pin(
            Port("reset", "I", 1, "reset", ip=self), (f"{gpio_name}/s_axi_aresetn",)
        )

        self._create_hier_pin(
            Port(
                "AXI",
                "I",
                width=None,
                protocol="xilinx.com:interface:aximm_rtl:1.0",
                mode="Slave",
                ip=self,
                addr_seg_name=f"{gpio_name}/S_AXI/Reg",
            ),
            (f"{gpio_name}/S_AXI",),
        )
        # self.assign_bd_address

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
            self.config_width2 = random.randint(1, 32)
            if self.config_dir2 in ("O", "IO"):
                self.config_default_out_val2 = random.choice(
                    (0, all_ones(self.config_width2), randintwidth(self.config_width2))
                )
            if self.config_dir2 in ("IO",):
                self.config_default_tristate_val2 = random.choice(
                    (0, all_ones(self.config_width2), randintwidth(self.config_width2))
                )

        # TODO: GPIO Interrupt
