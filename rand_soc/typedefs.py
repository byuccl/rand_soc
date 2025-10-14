import enum


class Protocol(enum.Enum):
    CLOCK = "clk"
    CLOCK_LOCKED = "clk_locked"
    RESET = "reset"
    RESET_PERIPHERAL = "reset_peripheral"
    RESET_PERIPHERAL_N = "reset_peripheral_n"
    RESET_INTERCONNECT = "reset_interconnect"
    RESET_MICROBLAZE = "reset_mb"
    DATA = "data"
    CONTROL = "control"
    AXI_STREAM = "xilinx.com:interface:axis_rtl:1.0"

    def is_xilinx_protocol(self):
        return self.value.startswith("xilinx.com:")

    def get_get_type(self):
        if self in (Protocol.AXI_STREAM,):
            return NetType.INTERFACE
        return NetType.WIRE


class NetType(enum.Enum):
    WIRE = "wire"
    INTERFACE = "interface"


class Direction(enum.Enum):
    OUTPUT = ("Master", "O")
    INPUT = ("Slave", "I")

    def get_str(self, net_type):
        if net_type == NetType.INTERFACE:
            return self.value[0]
        return self.value[1]

    @classmethod
    def from_str(cls, s):
        mapping = {
            "Master": cls.OUTPUT,
            "O": cls.OUTPUT,
            "Slave": cls.INPUT,
            "I": cls.INPUT,
        }
        if s not in mapping:
            raise ValueError(f"Unknown direction string: {s}")
        return mapping[s]
