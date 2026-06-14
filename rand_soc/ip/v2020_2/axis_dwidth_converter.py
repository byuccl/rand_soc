"""AXI Stream Data Width Converter IP.

Bridges a TDATA width mismatch between an AXIS source and sink. Inserted by
RandomDesign._connect_axis() when a source/sink pair has differing widths and the
config requests converters (``axi_stream.io_converters`` /
``axi_stream.internal_converters``).

The Xilinx converter is a byte gearbox: it requires the two TDATA byte widths to
have an integer ratio. The creator only instances it when that holds, so both
S and M byte counts are set explicitly here to pin the conversion deterministically.
"""

import math

from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class AxisDwidthConverter(IP):
    """AXI Stream Data Width Converter (S TDATA width -> M TDATA width)."""

    def __init__(self, design, name, in_width, out_width):
        super().__init__(design, name)
        self.in_width = in_width
        self.out_width = out_width
        self.instance()

    @property
    def name(self):
        return "axis_dwidth_converter"

    def instance(self):
        super().instance()

        inst = "axis_dwidth_converter_0"
        self._new_instance(
            "xilinx.com:ip:axis_dwidth_converter:1.1",
            inst,
            properties={
                "CONFIG.S_TDATA_NUM_BYTES": math.ceil(self.in_width / 8),
                "CONFIG.M_TDATA_NUM_BYTES": math.ceil(self.out_width / 8),
            },
        )

        # Clock and reset pins (connected by the creator's clock/reset passes).
        self.port_clk_in = self._create_hier_pin(
            "aclk", Protocol.CLOCK, Direction.INPUT, 1
        )
        self.port_clk_in.connect_internal(f"{inst}/aclk")
        self.port_reset_in = self._create_hier_pin(
            "aresetn", Protocol.RESET_INTERCONNECT, Direction.INPUT, 1
        )
        self.port_reset_in.connect_internal(f"{inst}/aresetn")

        # Slave input (from the source) and master output (to the sink).
        self.axi_in = self._create_hier_pin(
            "S_AXIS", Protocol.AXI_STREAM, Direction.INPUT, width=self.in_width
        )
        self.axi_in.connect_internal(f"{inst}/S_AXIS")

        self.axi_out = self._create_hier_pin(
            "M_AXIS", Protocol.AXI_STREAM, Direction.OUTPUT, width=self.out_width
        )
        self.axi_out.connect_internal(f"{inst}/M_AXIS")
