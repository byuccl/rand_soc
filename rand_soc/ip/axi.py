""" AXI Smartconnect IP """

from .ip_base import IP


class Axi(IP):
    """AXI Smartconnect IP class"""

    def __init__(self, design, name, num_masters, num_slaves):
        super().__init__(design, name)

        self.port_masters = []
        self.port_slaves = []
        self.instance(num_masters, num_slaves)

    @property
    def name(self):
        return "axi"

    def instance(self, num_masters, num_slaves):
        super().instance()

        axi_name = "axi_0"
        self._new_instance(
            "xilinx.com:ip:smartconnect:1.0",
            "axi_0",
            {
                "CONFIG.NUM_MI": num_slaves,
                "CONFIG.NUM_SI": num_masters,
            },
        )

        self._create_hier_pin("clk", "clk", "I", 1).connect_internal(f"{axi_name}/aclk")
        self._create_hier_pin("reset", "reset", "I", 1).connect_internal(
            f"{axi_name}/aresetn"
        )

        for i in range(num_masters):
            port = self._create_hier_pin(
                f"AXI_M{i}", "xilinx.com:interface:aximm_rtl:1.0", "Slave"
            )
            port.connect_internal(f"{axi_name}/S{i:02}_AXI")
            self.port_masters.append(port)

        for i in range(num_slaves):
            port = self._create_hier_pin(
                f"AXI_S{i}", "xilinx.com:interface:aximm_rtl:1.0", "Master"
            )
            port.connect_internal(f"{axi_name}/M{i:02}_AXI")
            self.port_slaves.append(port)
