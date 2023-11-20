from .ports import Port
from .ip import IP


class Microblaze(IP):
    """Microblaze class"""

    def __init__(self, name, axi_master=True):
        super().__init__(name)
        self.axi_master = axi_master

    def randomize(self):
        pass

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        self.instance_name = "microblaze_0"
        microblaze_config = {}
        if self.axi_master:
            microblaze_config["CONFIG.C_D_AXI"] = 1
        self.new_instance("xilinx.com:ip:microblaze:11.0", self.instance_name, microblaze_config)

        # Instruction memory
        mem_bus_insn_name = "lmb_i"
        mem_ctrl_insn_name = "lmb_ctrl_i"
        self.instance_str += "# Instruction memory\n"
        self.new_instance("xilinx.com:ip:lmb_v10:3.0", mem_bus_insn_name)
        self.new_instance("xilinx.com:ip:lmb_bram_if_cntlr:4.0", mem_ctrl_insn_name)
        self.connect_instance_pin(f"{self.instance_name}/ILMB", f"{mem_bus_insn_name}/LMB_M")
        self.connect_instance_pin(f"{mem_bus_insn_name}/LMB_Sl_0", f"{mem_ctrl_insn_name}/SLMB")

        # Data memory
        mem_bus_data_name = "lmb_d"
        mem_ctrl_data_name = "lmb_ctrl_d"
        self.instance_str += "# Data memory\n"
        self.new_instance("xilinx.com:ip:lmb_v10:3.0", mem_bus_data_name)
        self.new_instance("xilinx.com:ip:lmb_bram_if_cntlr:4.0", mem_ctrl_data_name)
        self.connect_instance_pin(f"{self.instance_name}/DLMB", f"{mem_bus_data_name}/LMB_M")
        self.connect_instance_pin(f"{mem_bus_data_name}/LMB_Sl_0", f"{mem_ctrl_data_name}/SLMB")

        # Memory
        self.instance_str += "# Memory\n"
        mem_name = "mem"
        self.new_instance(
            "xilinx.com:ip:blk_mem_gen:8.4",
            mem_name,
            properties={"CONFIG.Memory_Type": "True_Dual_Port_RAM"},
        )
        self.connect_instance_pin(f"{mem_ctrl_insn_name}/BRAM_PORT", f"{mem_name}/BRAM_PORTA")
        self.connect_instance_pin(f"{mem_ctrl_data_name}/BRAM_PORT", f"{mem_name}/BRAM_PORTB")

        # AXI
        if self.axi_master:
            self.instance_str += "# AXI\n"
            self.create_hier_pin(
                Port(
                    self,
                    "AXI",
                    "O",
                    width=None,
                    protocol="xilinx.com:interface:aximm_rtl:1.0",
                    mode="Master",
                ),
                (f"{instance_name}/M_AXI",),
            )
            axi_name = "axi"
            self.new_instance("xilinx.com:ip:axi_bram_ctrl:4.0", axi_name)
            self.connect_instance_pin(f"{mem_name}/BRAM_PORTA", f"{axi_name}/BRAM_PORTA")
            self.connect_instance_pin(f"{mem_name}/BRAM_PORTB", f"{axi_name}/BRAM_PORTB")

        # Create BD pins
        self.instance_str += "# Create BD pins\n"
        self.create_hier_pin(
            Port(self, "clk", "I", width=1, protocol="clk"),
            (
                f"{self.instance_name}/Clk",
                f"{mem_bus_insn_name}/LMB_Clk",
                f"{mem_ctrl_insn_name}/LMB_Clk",
                f"{mem_bus_data_name}/LMB_Clk",
                f"{mem_ctrl_data_name}/LMB_Clk",
            ),
        )

        self.create_hier_pin(
            Port(self, "reset", "I", width=1, protocol="reset"),
            (
                f"{self.instance_name}/Reset",
                f"{mem_bus_insn_name}/SYS_Rst",
                f"{mem_ctrl_insn_name}/LMB_Rst",
                f"{mem_bus_data_name}/SYS_Rst",
                f"{mem_ctrl_data_name}/LMB_Rst",
            ),
        )

    @property
    def name(self):
        return "microblaze"
