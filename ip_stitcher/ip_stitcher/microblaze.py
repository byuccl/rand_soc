from .ip import IP


class Microblaze(IP):
    """Microblaze class"""

    def __init__(self, name):
        super().__init__()
        self.hier_name = name

    def instance(self):
        self.instance_str += f"create_bd_cell -type hier {self.hier_name}\n"

        self.instance_name = "microblaze_0"
        self.new_instance("xilinx.com:ip:microblaze:11.0", self.instance_name)

        # Instruction memory
        insn_mem_name = "lmb_i"
        self.instance_str += "# Instruction memory\n"
        self.new_instance("xilinx.com:ip:lmb_v10:3.0", insn_mem_name)
        self.instance_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{self.instance_name}/ILMB] [get_bd_intf_pins {self.hier_name}/{insn_mem_name}/LMB_M]\n"

        # Data memory
        data_mem_name = "lmb_d"
        self.instance_str += "# Data memory\n"
        self.new_instance("xilinx.com:ip:lmb_v10:3.0", data_mem_name)
        self.instance_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{self.instance_name}/DLMB] [get_bd_intf_pins {self.hier_name}/{data_mem_name}/LMB_M]\n"

        # Create BD pins

    @property
    def name(self):
        return "microblaze"


# create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 lmb_v10_0

# connect_bd_intf_net [get_bd_intf_pins microblaze_0/DLMB] [get_bd_intf_pins lmb_v10_0/LMB_M]
