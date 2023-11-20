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

        instance_name = "microblaze_0"
        microblaze_config = {}
        if self.axi_master:
            microblaze_config["CONFIG.C_D_AXI"] = 1
        self._new_instance(
            "xilinx.com:ip:microblaze:11.0", instance_name, microblaze_config
        )

        # Instruction memory
        mem_bus_insn_name = "lmb_i"
        mem_ctrl_insn_name = "lmb_ctrl_i"
        self.instance_str += "# Instruction memory\n"
        self._new_instance("xilinx.com:ip:lmb_v10:3.0", mem_bus_insn_name)
        self._new_instance("xilinx.com:ip:lmb_bram_if_cntlr:4.0", mem_ctrl_insn_name)
        self._connect_instance_pin(
            f"{instance_name}/ILMB", f"{mem_bus_insn_name}/LMB_M"
        )
        self._connect_instance_pin(
            f"{mem_bus_insn_name}/LMB_Sl_0", f"{mem_ctrl_insn_name}/SLMB"
        )

        # Data memory
        mem_bus_data_name = "lmb_d"
        mem_ctrl_data_name = "lmb_ctrl_d"
        self.instance_str += "# Data memory\n"
        self._new_instance("xilinx.com:ip:lmb_v10:3.0", mem_bus_data_name)
        self._new_instance("xilinx.com:ip:lmb_bram_if_cntlr:4.0", mem_ctrl_data_name)
        self._connect_instance_pin(
            f"{instance_name}/DLMB", f"{mem_bus_data_name}/LMB_M"
        )
        self._connect_instance_pin(
            f"{mem_bus_data_name}/LMB_Sl_0", f"{mem_ctrl_data_name}/SLMB"
        )

        # Memory
        self.instance_str += "# Memory\n"
        mem_name = "mem"
        self._new_instance(
            "xilinx.com:ip:blk_mem_gen:8.4",
            mem_name,
            properties={"CONFIG.Memory_Type": "True_Dual_Port_RAM"},
        )
        self._connect_instance_pin(
            f"{mem_ctrl_insn_name}/BRAM_PORT", f"{mem_name}/BRAM_PORTA"
        )
        self._connect_instance_pin(
            f"{mem_ctrl_data_name}/BRAM_PORT", f"{mem_name}/BRAM_PORTB"
        )

        # AXI
        if self.axi_master:
            self.instance_str += "# AXI\n"
            self._create_hier_pin(
                Port(
                    "AXI",
                    "O",
                    width=None,
                    protocol="xilinx.com:interface:aximm_rtl:1.0",
                    mode="Master",
                    ip=self,
                    addr_seg_name=f"{instance_name}/Data",
                ),
                (f"{instance_name}/M_AXI_DP",),
            )

        # Address space
        self._assign_bd_address(f"{instance_name}/Data", "lmb_ctrl_d/SLMB/Mem")
        self._assign_bd_address(f"{instance_name}/Instruction", "lmb_ctrl_i/SLMB/Mem")

        # Create BD pins
        self.instance_str += "# Create BD pins\n"
        self._create_hier_pin(
            Port("clk", "I", width=1, protocol="clk", ip=self),
            (
                f"{instance_name}/Clk",
                f"{mem_bus_insn_name}/LMB_Clk",
                f"{mem_ctrl_insn_name}/LMB_Clk",
                f"{mem_bus_data_name}/LMB_Clk",
                f"{mem_ctrl_data_name}/LMB_Clk",
            ),
        )

        self._create_hier_pin(
            Port("reset", "I", width=1, protocol="reset", ip=self),
            (
                f"{instance_name}/Reset",
                f"{mem_bus_insn_name}/SYS_Rst",
                f"{mem_ctrl_insn_name}/LMB_Rst",
                f"{mem_bus_data_name}/SYS_Rst",
                f"{mem_ctrl_data_name}/LMB_Rst",
            ),
        )

        self._create_hier_pin(
            Port(
                "interrupt",
                "I",
                protocol="xilinx.com:interface:mbinterrupt_rtl:1.0",
                mode="Slave",
                ip=self,
            ),
            (f"{instance_name}/INTERRUPT",),
        )

    @property
    def name(self):
        return "microblaze"
