"""Interrupt controller IP"""

from .ip_base import IP


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

        self.port_clk_in = self._create_hier_pin("clk_in", "clk", "I", 1)
        self.port_clk_in.connect_internal(f"{reset_name}/slowest_sync_clk")

        self.port_reset_in = self._create_hier_pin("reset_in", "reset", "I", 1)
        self.port_reset_in.connect_internal(f"{reset_name}/ext_reset_in")

        self.port_dcm_locked = self._create_hier_pin("dcm_locked", "clk_locked", "I", 1)
        self.port_dcm_locked.connect_internal(f"{reset_name}/dcm_locked")

        self.port_mb_reset = self._create_hier_pin("mb_reset", "reset_mb", "O", 1)
        self.port_mb_reset.connect_internal(f"{reset_name}/mb_reset")
        self.port_mb_reset.connected = True

        self.port_peripheral_areset_n = self._create_hier_pin(
            "peripheral_areset_n", "reset_peripheral_n", "O", 1
        )
        self.port_peripheral_areset_n.connect_internal(
            f"{reset_name}/peripheral_aresetn"
        )
        self.port_peripheral_areset_n.connected = True

        self.port_peripheral_areset = self._create_hier_pin(
            "peripheral_areset", "reset_peripheral", "O", 1
        )
        self.port_peripheral_areset.connect_internal(f"{reset_name}/peripheral_areset")
        self.port_peripheral_areset.connected = True

        self.port_interconnect_aresetn = self._create_hier_pin(
            "interconnect_aresetn", "reset_interconnect", "O", 1
        )
        self.port_interconnect_aresetn.connect_internal(
            f"{reset_name}/interconnect_aresetn"
        )
        self.port_interconnect_aresetn.connected = True
