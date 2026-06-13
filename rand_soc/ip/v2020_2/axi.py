"""AXI Smartconnect and AXI Interconnect IP"""

from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class AxiSmartconnect(IP):
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

        self._create_hier_pin(
            "clk", Protocol.CLOCK, Direction.INPUT, 1
        ).connect_internal(f"{axi_name}/aclk")
        self._create_hier_pin(
            "reset", Protocol.RESET_INTERCONNECT, Direction.INPUT, 1
        ).connect_internal(f"{axi_name}/aresetn")

        for i in range(num_masters):
            port = self._create_hier_pin(f"AXI_M{i}", Protocol.AXI_MM, Direction.INPUT)
            port.connect_internal(f"{axi_name}/S{i:02}_AXI")
            self.port_masters.append(port)

        for i in range(num_slaves):
            port = self._create_hier_pin(f"AXI_S{i}", Protocol.AXI_MM, Direction.OUTPUT)
            port.connect_internal(f"{axi_name}/M{i:02}_AXI")
            self.port_slaves.append(port)


class AxiInterconnect(IP):
    """AXI Interconnect IP class"""

    def __init__(self, design, name, num_masters, num_slaves):
        super().__init__(design, name)

        self.port_masters = []
        self.port_slaves = []
        self.instance(num_masters, num_slaves)

    @property
    def name(self):
        return "axi_legacy"

    def instance(self, num_masters, num_slaves):
        super().instance()

        axi_name = "axi_0"
        self._new_instance(
            "xilinx.com:ip:axi_interconnect:2.1",
            "axi_0",
            {
                "CONFIG.NUM_MI": num_slaves,
                "CONFIG.NUM_SI": num_masters,
            },
        )

        clk_pin = self._create_hier_pin("clk", Protocol.CLOCK, Direction.INPUT, 1)
        clk_pin.connect_internal(f"{axi_name}/ACLK")

        reset_pin = self._create_hier_pin(
            "reset", Protocol.RESET_INTERCONNECT, Direction.INPUT, 1
        )
        reset_pin.connect_internal(f"{axi_name}/ARESETN")

        for i in range(num_masters):
            port = self._create_hier_pin(f"AXI_M{i}", Protocol.AXI_MM, Direction.INPUT)
            port.connect_internal(f"{axi_name}/S{i:02}_AXI")
            clk_pin.connect_internal(f"{axi_name}/S{i:02}_ACLK")
            reset_pin.connect_internal(f"{axi_name}/S{i:02}_ARESETN")
            self.port_masters.append(port)

        for i in range(num_slaves):
            port = self._create_hier_pin(f"AXI_S{i}", Protocol.AXI_MM, Direction.OUTPUT)
            port.connect_internal(f"{axi_name}/M{i:02}_AXI")
            clk_pin.connect_internal(f"{axi_name}/M{i:02}_ACLK")
            reset_pin.connect_internal(f"{axi_name}/M{i:02}_ARESETN")
            self.port_slaves.append(port)
