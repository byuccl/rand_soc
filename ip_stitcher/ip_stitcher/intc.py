""" GPIO IP """


from .ports import Port
from .ip import IP


class Intc(IP):
    """Interrupt controller IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)
        self.port_clk = None
        self.port_reset = None

        self.instance()

    @property
    def name(self):
        return "intc"

    def instance(self):
        super().instance()

        intc_name = "intc_0"
        self._new_instance("xilinx.com:ip:axi_intc:4.1", intc_name)

        self.port_clk = self._create_hier_pin("clk", "clk", "I", 1)
        self.port_clk.connect(f"{intc_name}/s_axi_aclk")
        self.port_reset = self._create_hier_pin("reset", "reset", "I", 1)
        self.port_reset.connect(f"{intc_name}/s_axi_aresetn")
        self.port_axi = self._create_hier_pin(
            "AXI", "xilinx.com:interface:aximm_rtl:1.0", "Slave"
        )
