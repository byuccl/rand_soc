"""Interrupt controller IP"""

from rand_soc.typedefs import Direction, Protocol
from ..ip_base import IP


class SystemReset(IP):
    """Interrupt controller IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)
        self.port_clk_in = None
        self.port_reset_in = None
        self.port_dcm_locked = None
        self.port_mb_reset = None
        self.port_peripheral_areset_n = None
        self.port_interconnect_aresetn = None

        self.instance()

    @property
    def name(self):
        return "reset"

    def instance(self):
        super().instance()

        reset_name = "reset_0"
        self._new_instance("xilinx.com:ip:proc_sys_reset:5.0", reset_name)

        self.port_clk_in = self._create_hier_pin(
            "clk_in", Protocol.CLOCK, Direction.INPUT, 1
        )
        self.port_clk_in.connect_internal(f"{reset_name}/slowest_sync_clk")

        self.port_reset_in = self._create_hier_pin(
            "reset_in", Protocol.RESET, Direction.INPUT, 1
        )
        self.port_reset_in.connect_internal(f"{reset_name}/ext_reset_in")

        self.port_dcm_locked = self._create_hier_pin(
            "dcm_locked", Protocol.CLOCK_LOCKED, Direction.INPUT, 1
        )
        self.port_dcm_locked.connect_internal(f"{reset_name}/dcm_locked")

        self.port_mb_reset = self._create_hier_pin(
            "mb_reset", Protocol.RESET_MICROBLAZE, Direction.OUTPUT, 1
        )
        self.port_mb_reset.connect_internal(f"{reset_name}/mb_reset")
        self.port_mb_reset.connected = True

        self.port_peripheral_areset_n = self._create_hier_pin(
            "peripheral_areset_n", Protocol.RESET_PERIPHERAL_N, Direction.OUTPUT, 1
        )
        self.port_peripheral_areset_n.connect_internal(
            f"{reset_name}/peripheral_aresetn"
        )
        self.port_peripheral_areset_n.connected = True

        self.port_peripheral_reset = self._create_hier_pin(
            "peripheral_areset", Protocol.RESET_PERIPHERAL, Direction.OUTPUT, 1
        )
        self.port_peripheral_reset.connect_internal(f"{reset_name}/peripheral_reset")
        self.port_peripheral_reset.connected = True

        self.port_interconnect_aresetn = self._create_hier_pin(
            "interconnect_aresetn", Protocol.RESET_INTERCONNECT, Direction.OUTPUT, 1
        )
        self.port_interconnect_aresetn.connect_internal(
            f"{reset_name}/interconnect_aresetn"
        )
        self.port_interconnect_aresetn.connected = True
