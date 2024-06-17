""" Clk Gen IP """

from .ip_base import IP


class ClkGen(IP):
    """Clock Generator IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)
        self.port_clk_in = None
        self.port_clk_out = None

        self.instance()

    @property
    def name(self):
        return "clk_wiz"

    def instance(self):
        super().instance()

        clk_gen_name = "clk_wiz_0"
        self._new_instance("xilinx.com:ip:clk_wiz:6.0", clk_gen_name)

        self.port_clk_in = self._create_hier_pin("clk_in", "clk", "I", 1)
        self.port_clk_in.connect_internal(f"{clk_gen_name}/clk_in1")

        self.port_clk_out = self._create_hier_pin("clk_out", "clk", "O", 1)
        self.port_clk_out.connect_internal(f"{clk_gen_name}/clk_out1")

        self._create_hier_pin("reset", "reset", "I", 1).connect_internal(
            f"{clk_gen_name}/reset"
        )
