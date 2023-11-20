""" UARTLite IP """

import random

from .ports import Port
from .ip import IP


class Uartlite(IP):
    def __init__(self, name):
        super().__init__(name)
        self.config_baud_rate = None
        self.config_parity = None

    @property
    def name(self):
        return "uartlite"

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        uart_name = "uart_0"
        config = {}
        config["CONFIG.C_BAUDRATE"] = self.config_baud_rate
        config["CONFIG.PARITY"] = self.config_parity

        self._new_instance("xilinx.com:ip:axi_uartlite:2.0", uart_name, config)

        self._create_hier_pin(
            Port(
                "UART",
                protocol="xilinx.com:interface:uart_rtl:1.0",
                mode="Master",
                ip=self,
            ),
            (f"{uart_name}/UART",),
        )

        self.instance_str += "# Create BD pins\n"
        self._create_hier_pin(
            Port("clk", "I", 1, "clk", ip=self), (f"{uart_name}/s_axi_aclk",)
        )
        self._create_hier_pin(
            Port("reset", "I", 1, "reset", ip=self), (f"{uart_name}/s_axi_aresetn",)
        )
        self._create_hier_pin(
            Port(
                "AXI",
                "I",
                protocol="xilinx.com:interface:aximm_rtl:1.0",
                mode="Slave",
                ip=self,
                addr_seg_name=f"{uart_name}/S_AXI/Reg",
            ),
            (f"{uart_name}/S_AXI",),
        )

    def randomize(self):
        self.config_baud_rate = random.choice(
            [
                110,
                300,
                1200,
                2400,
                4800,
                9600,
                19200,
                38400,
                57600,
                115200,
                128000,
                230400,
            ]
        )
        self.config_parity = random.choice(("No_Parity", "Odd", "Even"))
