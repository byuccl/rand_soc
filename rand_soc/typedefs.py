import enum


class Protocols(enum.Enum):
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


OUTPUT_DIRECTIONS = ("Master", "O")
INPUT_DIRECTIONS = ("Slave", "I")
