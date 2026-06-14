"""JTAG-to-AXI Master IP.

A pin-free AXI master driven over the device JTAG/BSCAN chain. Used as the
implicit AXI master when a design has no internal master and the config selects
the ``jtag`` no-master strategy (``axi_mm.no_master``). Unlike an external AXI
port it consumes no top-level package pins, so it avoids the I/O-placement
overflow that a full external AXI bus causes.

This is a hand-built IP (like the AXIS broadcaster/combiner) because it is
instanced mid-flow by the creator rather than selected from ``available_ip``.
"""

import random

from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class JtagAxi(IP):
    """JTAG-to-AXI Master."""

    def __init__(self, design, name):
        super().__init__(design, name)
        self.instance()

    @property
    def name(self):
        return "jtag_axi"

    def instance(self):
        super().instance()

        inst = "jtag_axi_0"
        protocol = random.choice(["AXI4", "AXI4LITE"])
        self._new_instance(
            "xilinx.com:ip:jtag_axi:1.2",
            inst,
            properties={"CONFIG.PROTOCOL": protocol},
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

        # AXI master output -- drives the interconnect/smartconnect. Collected by
        # RandomDesign._axi() like any other AXI master port.
        self.master_port = self._create_hier_pin(
            "M_AXI", Protocol.AXI_MM, Direction.OUTPUT
        )
        self.master_port.connect_internal(f"{inst}/M_AXI")
