""" UARTLite IP """

from .ip_base import IPrandom


class Uartlite(IPrandom):
    @property
    def name(self):
        return "uartlite"

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()
        return

        super().instance()

        uart_name = "uart_0"
        config = {}
        config["CONFIG.C_BAUDRATE"] = self.config_baud_rate
        config["CONFIG.PARITY"] = self.config_parity

        self._new_instance("xilinx.com:ip:axi_uartlite:2.0", uart_name, config)

        self._bd_tcl += "# Create BD pins\n"
        # self._create_hier_pin("clk", "clk", "I", 1).connect_internal(
        #     f"{uart_name}/s_axi_aclk"
        # )
        # self._create_hier_pin("reset", "reset", "I", 1).connect_internal(
        #     f"{uart_name}/s_axi_aresetn"
        # )
        self._create_hier_pin(
            "AXI",
            "xilinx.com:interface:aximm_rtl:1.0",
            "Slave",
            addr_seg_name=f"{uart_name}/S_AXI/Reg",
        ).connect_internal(f"{uart_name}/S_AXI")
        # self._create_hier_pin(
        #     "UART", "xilinx.com:interface:uart_rtl:1.0", "Master"
        # ).connect_internal(f"{uart_name}/UART")
        self._create_hier_pin("irq", "irq", "O", 1).connect_internal(
            f"{uart_name}/interrupt"
        )

    def randomize(self):
        self.load_data_from_yaml(__file__)
