from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class AxisBroadcaster(IP):
    pass

    def __init__(self, design, name, port_driver, fanout_degree):
        super().__init__(design, name)
        self.port_driver = port_driver
        self.fanout_degree = fanout_degree

        self.instance()

    @property
    def name(self):
        return "axis_broadcaster"

    def instance(self):
        super().instance()

        axis_broadcaster_name = "axis_broadcaster_0"
        self._new_instance(
            "xilinx.com:ip:axis_broadcaster:1.1",
            axis_broadcaster_name,
            properties={"CONFIG.NUM_MI": self.fanout_degree},
        )

        # Clock and reset ports
        self.port_clk_in = self._create_hier_pin(
            "aclk", Protocol.CLOCK, Direction.INPUT, 1
        )
        self.port_clk_in.connect_internal(f"{axis_broadcaster_name}/aclk")
        self.port_reset_in = self._create_hier_pin(
            "aresetn", Protocol.RESET_INTERCONNECT, Direction.INPUT, 1
        )
        self.port_reset_in.connect_internal(f"{axis_broadcaster_name}/aresetn")

        # AXI In Port
        self.axi_in = self._create_hier_pin(
            "S_AXIS", Protocol.AXI_STREAM, Direction.INPUT, width=self.port_driver.width
        )
        self.axi_in.connect_internal(f"{axis_broadcaster_name}/S_AXIS")
        self.port_driver.connect(self.axi_in)

        # AXI Out Ports
        self.axi_out_ports = {}
        for i in range(self.fanout_degree):
            self.axi_out_ports[i] = self._create_hier_pin(
                f"M_AXIS_{i}",
                Protocol.AXI_STREAM,
                Direction.OUTPUT,
                width=self.port_driver.width,
            )
            self.axi_out_ports[i].connect_internal(
                f"{axis_broadcaster_name}/M{i:02d}_AXIS"
            )

    def get_output_port(self, idx):
        return self.axi_out_ports[idx]
