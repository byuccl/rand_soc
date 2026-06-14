from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class AxisCombiner(IP):
    """AXI Stream Combiner: merges several AXI Stream sources into a single sink.

    The combined master output drives ``port_sink``; each of the ``source_widths``
    slave inputs is connected to one of the sources by the caller via
    ``get_input_port``.
    """

    def __init__(self, design, name, port_sink, source_widths):
        super().__init__(design, name)
        self.port_sink = port_sink
        self.source_widths = list(source_widths)
        self.fanin_degree = len(self.source_widths)

        self.instance()

    @property
    def name(self):
        return "axis_combiner"

    def instance(self):
        super().instance()

        axis_combiner_name = "axis_combiner_0"
        self._new_instance(
            "xilinx.com:ip:axis_combiner:1.1",
            axis_combiner_name,
            properties={"CONFIG.NUM_SI": self.fanin_degree},
        )

        # Clock and reset ports
        self.port_clk_in = self._create_hier_pin(
            "aclk", Protocol.CLOCK, Direction.INPUT, 1
        )
        self.port_clk_in.connect_internal(f"{axis_combiner_name}/aclk")
        self.port_reset_in = self._create_hier_pin(
            "aresetn", Protocol.RESET_INTERCONNECT, Direction.INPUT, 1
        )
        self.port_reset_in.connect_internal(f"{axis_combiner_name}/aresetn")

        # AXI In Ports (one slave interface per source being combined)
        self.axi_in_ports = {}
        for i, width in enumerate(self.source_widths):
            self.axi_in_ports[i] = self._create_hier_pin(
                f"S_AXIS_{i}", Protocol.AXI_STREAM, Direction.INPUT, width=width
            )
            self.axi_in_ports[i].connect_internal(f"{axis_combiner_name}/S{i:02d}_AXIS")

        # AXI Out Port: the combiner concatenates its inputs, so its true width is
        # the sum of the combined widths. The caller wires this to the sink
        # (through a width converter when needed) rather than connecting here, so
        # the output leg gets the same converter handling as every other leg.
        self.axi_out = self._create_hier_pin(
            "M_AXIS",
            Protocol.AXI_STREAM,
            Direction.OUTPUT,
            width=sum(self.source_widths),
        )
        self.axi_out.connect_internal(f"{axis_combiner_name}/M_AXIS")

    def get_input_port(self, idx):
        return self.axi_in_ports[idx]
