import abc

from rand_soc.typedefs import ConverterReq, Direction, NetType, Protocol


class Port:
    """A port on an IP, either external or internal"""

    __metaclass__ = abc.ABCMeta

    def __init__(self, name, protocol, direction, width=None):
        self.name = name

        assert isinstance(direction, Direction)
        self.direction = direction

        assert isinstance(protocol, Protocol)
        self.protocol = protocol

        if self.protocol.get_type() == NetType.WIRE:
            assert width is not None, f"Port {name} has no width"
        self.width = width

        self.connected = False

        # Whether a connector driving this sink must route through a width
        # converter rather than letting an upstream stream land directly. Set on
        # IP slave ports that validate TDATA width and/or field structure (e.g.
        # the AXI DMA stream slaves, the CORDIC inputs); the lenient default is
        # NONE. See ConverterReq for the meaning of each level.
        self.converter_req = ConverterReq.NONE


class IpPort(Port):
    """IP Port"""

    def __init__(
        self, ip, name, protocol, direction, *, width=None, addr_segs=None,
        converter_req=ConverterReq.NONE,
    ):
        super().__init__(name, protocol, direction, width)
        self.converter_req = converter_req
        self.ip = ip
        self.ip.ports.append(self)

        if addr_segs:
            assert (
                protocol.get_type() == NetType.INTERFACE
            ), f"Only interface ports can have address segments. {ip.name}/{name} has protocol {protocol} and addr_segs {addr_segs}"
        self.addr_segs = [] if addr_segs is None else addr_segs

        if self.protocol.get_type() == NetType.INTERFACE:
            self.ip._bd_tcl += f"create_bd_intf_pin -mode {self.direction.get_str(NetType.INTERFACE)} -vlnv {self.protocol.value} {self.hier_name}\n"
        else:
            self.ip._bd_tcl += f"create_bd_pin -dir {self.direction.get_str(NetType.WIRE)} -from {self.width-1} -to 0 {self.hier_name}\n"

    @property
    def hier_name(self):
        return f"{self.ip.hier_name}/{self.name}"

    @property
    def hier_name_w(self):
        return f"{self.ip.hier_name}/{self.name}({self.width})"

    def __repr__(self) -> str:
        return f"IpPort({self.hier_name}, {self.direction}, {self.protocol}, {self.width}, {self.addr_segs})"

    def connect(self, port):
        """Connect this port to a top-level port, another IP port"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, (ExternalPort, IpPort))
        if isinstance(port, ExternalPort):
            port.connect(self)
        else:
            if self.protocol.get_type() == NetType.WIRE:
                self.ip.design.ip_to_ip_connections_tcl += f"connect_bd_net [get_bd_pins {self.hier_name}] [get_bd_pins {port.hier_name}]\n"
            else:
                self.ip.design.ip_to_ip_connections_tcl += f"connect_bd_intf_net -boundary_type upper [get_bd_intf_pins {self.hier_name}] [get_bd_intf_pins {port.hier_name}]\n"

            self.connected = True
            port.connected = True

    def connect_internal(self, port_name):
        """Connect this port to an internal port"""
        if isinstance(port_name, (list, tuple)):
            for p in port_name:
                self.connect_internal(p)
            return

        if self.protocol.get_type() == NetType.WIRE:
            self.ip._bd_tcl += f"connect_bd_net [get_bd_pins {self.hier_name}] [get_bd_pins {self.ip.hier_name}/{port_name}]\n"
        else:
            self.ip._bd_tcl += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}] [get_bd_intf_pins {self.ip.hier_name}/{port_name}]\n"

        # Register AXI-Stream pins for post-validate width verification: compare
        # the IP's resolved TDATA width against the width the generator declared.
        if self.protocol == Protocol.AXI_STREAM and self.width is not None:
            self.ip.design.register_width_check(
                f"{self.ip.hier_name}/{port_name}", self.width, self.hier_name
            )


class ExternalPort(Port):
    """Top-level port"""

    def __init__(self, design, name, protocol, direction, width=None, properties=None):
        super().__init__(name, protocol, direction, width=width)
        self.design = design
        self.properties = properties

        if self.protocol.get_type() == NetType.INTERFACE:
            design._bd_tcl += f"create_bd_intf_port -mode {self.direction.get_str(NetType.INTERFACE)} -vlnv {self.protocol.value} {self.name}\n"
        else:
            design._bd_tcl += f"create_bd_port -dir {self.direction.get_str(NetType.WIRE)} -from {self.width-1} -to 0 {self.name}\n"
            assert properties is None, "Regular ports cannot have properties"

        if properties:
            prop = ""
            for key in sorted(properties.keys()):
                prop += f"{key} {properties[key]} "

            design._bd_tcl += (
                f'set_property -dict "{prop}" [get_bd_intf_ports {self.hier_name}]\n'
            )

    def connect(self, port):
        """Connect this port to an IP port(s)"""

        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, IpPort), type(port)
        assert (
            self.protocol == port.protocol
        ), f"Cannot connect {self.protocol} to {port.protocol}"

        if self.protocol.get_type() == NetType.WIRE:
            self.design._bd_tcl += f"connect_bd_net [get_bd_pins {self.name}] [get_bd_pins {port.hier_name}]\n"
        else:
            self.design._bd_tcl += f"connect_bd_intf_net [get_bd_intf_pins {self.name}] [get_bd_intf_pins {port.hier_name}]\n"
        port.connected = True

    @property
    def hier_name(self):
        return f"{self.name}"

    @property
    def hier_name_w(self):
        return f"{self.name}({self.width})"
