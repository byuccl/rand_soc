""" UARTLite IP """

import random

from .ip import IPrandom


class Uartlite(IPrandom):
    def __init__(self, design, name):
        super().__init__(design, name)
        self.config_baud_rate = None
        self.config_parity = None

    @property
    def name(self):
        return "uartlite"

    def instance(self):
        super().instance()

        uart_name = "uart_0"
        config = {}
        config["CONFIG.C_BAUDRATE"] = self.config_baud_rate
        config["CONFIG.PARITY"] = self.config_parity

        self._new_instance("xilinx.com:ip:axi_uartlite:2.0", uart_name, config)

        self._bd_tcl += "# Create BD pins\n"
        self._create_hier_pin("clk", "clk", "I", 1).connect_internal(
            f"{uart_name}/s_axi_aclk"
        )
        self._create_hier_pin("reset", "reset", "I", 1).connect_internal(
            f"{uart_name}/s_axi_aresetn"
        )
        self._create_hier_pin(
            "AXI",
            "xilinx.com:interface:aximm_rtl:1.0",
            "Slave",
            addr_seg_name=f"{uart_name}/S_AXI/Reg",
        ).connect_internal(f"{uart_name}/S_AXI")
        self._create_hier_pin(
            "UART", "xilinx.com:interface:uart_rtl:1.0", "Master"
        ).connect_internal(f"{uart_name}/UART")
        self._create_hier_pin("irq", "irq", "O", 1).connect_internal(
            f"{uart_name}/interrupt"
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
