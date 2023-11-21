""" GPIO IP """


from .ports import Port
from .ip import IP


class ClkGen(IP):
    """Interrupt controller IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)
        self.port_clk_in = None
        self.port_clk_out = None

        self.instance()

    @property
    def name(self):
        return "intc"

    def instance(self):
        super().instance()

        clk_gen_name = "clk_wiz_0"
        self._new_instance("xilinx.com:ip:clk_wiz:6.0", clk_gen_name)

        self.port_clk_in = self._create_hier_pin("clk_in", "clk", "I", 1)
        self.port_clk_in.connect(f"{clk_gen_name}/clk_in1")

        self.port_clk_out = self._create_hier_pin("clk_out", "clk", "O", 1)
        self.port_clk_out.connect(f"{clk_gen_name}/clk_out1")

        self._create_hier_pin("reset", "reset", "I", 1).connect(f"{clk_gen_name}/reset")

        # self.port_clk = self._create_hier_pin(
        #     Port("clk", "I", 1, "clk", ip=self), (f"{intc_name}/s_axi_aclk",)
        # )
        # self.port_reset = self._create_hier_pin(
        #     Port("reset", "I", 1, "reset", ip=self), (f"{intc_name}/s_axi_aresetn",)
        # )
