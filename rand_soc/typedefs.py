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
    IRQ = "irq"

    # Xilinx interface protocols. Those that get special connection handling are
    # named explicitly and referenced elsewhere (AXI_STREAM, AXI_MM,
    # MB_INTERRUPT); the rest are generic interfaces that are simply exported to
    # the top level (see RandomDesign._external_interfaces). When a new IP
    # introduces a protocol not listed here, instancing will raise
    # "is not a valid Protocol" -- just add the new member below.
    AXI_STREAM = "xilinx.com:interface:axis_rtl:1.0"
    AXI_MM = "xilinx.com:interface:aximm_rtl:1.0"
    MB_INTERRUPT = "xilinx.com:interface:mbinterrupt_rtl:1.0"
    ARB = "xilinx.com:interface:arb_rtl:1.0"
    CAN = "xilinx.com:interface:can_rtl:1.0"
    DIFF_ANALOG_IO = "xilinx.com:interface:diff_analog_io_rtl:1.0"
    EMC = "xilinx.com:interface:emc_rtl:1.0"
    GPIO = "xilinx.com:interface:gpio_rtl:1.0"
    ICAP = "xilinx.com:interface:icap_rtl:1.0"
    IIC = "xilinx.com:interface:iic_rtl:1.0"
    MDIO = "xilinx.com:interface:mdio_rtl:1.0"
    MII = "xilinx.com:interface:mii_rtl:1.0"
    SPI = "xilinx.com:interface:spi_rtl:1.0"
    STARTUP = "xilinx.com:interface:startup_rtl:1.0"
    STARTUP_IO = "xilinx.com:display_startup_io:startup_io_rtl:1.0"
    UART = "xilinx.com:interface:uart_rtl:1.0"
    ULPI = "xilinx.com:interface:ulpi_rtl:1.0"

    def is_xilinx_protocol(self):
        return self.value.startswith("xilinx.com:")

    def get_type(self):
        # Every Xilinx interface protocol is an interface net; everything else
        # (clk, reset, data, control, irq) is a plain wire.
        return NetType.INTERFACE if self.is_xilinx_protocol() else NetType.WIRE


class ConverterReq(enum.Enum):
    """Whether a width converter must be inserted on an AXI-Stream sink.

    NONE          -- no converter is required for this sink; one may still be
                     inserted opportunistically on a width difference per the
                     config's converter policy (random/yes). The lenient default.
    ON_WIDTH_DIFF -- a converter is mandatory whenever the source and sink TDATA
                     widths differ (e.g. the AXI DMA stream slaves, which
                     hard-error on a propagated width mismatch). Matching widths
                     connect directly.
    ALWAYS        -- a converter is mandatory even when the widths already match.
                     It flattens any structured-TDATA field map (e.g. CORDIC's
                     xn_re/xn_im fields) into a plain stream the sink accepts, so
                     a same-width foreign source never lands directly on it.
    """

    NONE = "none"
    ON_WIDTH_DIFF = "on_width_diff"
    ALWAYS = "always"

    @classmethod
    def from_yaml(cls, value):
        """Resolve a port's ``converter_req`` yaml value. An absent key (None)
        defaults to NONE."""
        if value is None:
            return cls.NONE
        return cls(value)


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
