""" Interrupt controller IP """

from .ip_base import IP


class Intc(IP):
    """Interrupt controller IP class"""

    def __init__(self, design, name, num_inputs):
        super().__init__(design, name)
        self.port_clk = None
        self.port_reset = None
        self.input_ports = []
        self.port_irq = None

        self.instance(num_inputs)

    @property
    def name(self):
        return "intc"

    def instance(self, num_inputs):
        super().instance()

        intc_name = "intc_0"
        self._new_instance("xilinx.com:ip:axi_intc:4.1", intc_name)

        concat_name = "concat_0"
        self._new_instance(
            "xilinx.com:ip:xlconcat:2.1", concat_name, {"CONFIG.NUM_PORTS": num_inputs}
        )
        self._connect_internal_pins_regular(f"{concat_name}/dout", f"{intc_name}/intr")

        self.port_clk = self._create_hier_pin("clk", "clk", "I", 1)
        self.port_clk.connect_internal(f"{intc_name}/s_axi_aclk")
        self.port_reset = self._create_hier_pin("reset", "reset", "I", 1)
        self.port_reset.connect_internal(f"{intc_name}/s_axi_aresetn")
        self.port_axi = self._create_hier_pin(
            "AXI",
            "xilinx.com:interface:aximm_rtl:1.0",
            "Slave",
            addr_segs=[f"{intc_name}/S_AXI/Reg"],
        ).connect_internal(f"{intc_name}/s_axi")

        for i in range(num_inputs):
            port = self._create_hier_pin(f"irq_{i}", "irq", "I", 1)
            port.connect_internal(f"{concat_name}/In{i}")
            self.input_ports.append(port)

        self.port_irq = self._create_hier_pin(
            "irq", "xilinx.com:interface:mbinterrupt_rtl:1.0", "Master"
        )
        self.port_irq.connect_internal(f"{intc_name}/interrupt")
