import abc

from rand_soc.typedefs import Direction, Protocol


class Port:
    """A port on an IP, either external or internal"""

    __metaclass__ = abc.ABCMeta

    def __init__(self, name, protocol, direction, width=None):
        self.name = name

        assert isinstance(direction, Direction)
        self.direction = direction
        self.width = width

        assert isinstance(protocol, Protocol)
        self.protocol = protocol
        self.connected = False


class IpPort(Port):
    """IP Port"""

    def __init__(self, ip, name, protocol, direction, width=None):
        super().__init__(name, protocol, direction, width)
        self.ip = ip
        self.ip.ports.append(self)

    @property
    def hier_name(self):
        return f"{self.ip.hier_name}/{self.name}"


class IpPortRegular(IpPort):
    """IP regular port"""

    def __init__(self, ip, name, protocol, direction, width):
        assert width, f"Port {name} has no width"
        super().__init__(ip, name, protocol, direction, width)
        self.ip._bd_tcl += f"create_bd_pin -dir {self.direction} -from {self.width-1} -to 0 {self.hier_name}\n"

    def __repr__(self) -> str:
        return f"IpPortRegular({self.hier_name}, {self.direction}, {self.width}, {self.protocol})"

    def connect(self, port):
        """Connect this port to a top-level port, another IP port"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, (ExternalPortRegular, IpPortRegular))
        if isinstance(port, ExternalPortRegular):
            port.connect(self)
        else:
            self.ip.design.ip_to_ip_connections_tcl += f"connect_bd_net [get_bd_pins {self.hier_name}] [get_bd_pins {port.hier_name}]\n"
            self.connected = True
            port.connected = True

    def connect_internal(self, port_name):
        """Connect this port to an internal port"""
        if isinstance(port_name, (list, tuple)):
            for p in port_name:
                self.connect_internal(p)
            return

        self.ip._bd_tcl += f"connect_bd_net [get_bd_pins {self.hier_name}] [get_bd_pins {self.ip.hier_name}/{port_name}]\n"


class IpPortInterface(IpPort):
    """IP interface port"""

    def __init__(
        self,
        ip,
        name,
        protocol,
        direction,
        *,
        width=None,
        addr_segs=None,
    ):
        super().__init__(ip, name, protocol, direction, width)
        if addr_segs is None:
            self.addr_segs = []
        else:
            self.addr_segs = addr_segs
        self.ip._bd_tcl += f"create_bd_intf_pin -mode {self.direction} -vlnv {self.protocol.value} {self.hier_name}\n"

    def __repr__(self) -> str:
        return f"IpPortInterface({self.hier_name}, {self.direction}, {self.protocol}, {self.addr_segs})"

    def connect(self, port):
        """Connect this port to a top-level port, another IP port"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, (ExternalPortInterface, IpPortInterface)), type(port)
        if isinstance(port, ExternalPortInterface):
            port.connect(self)
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

        self.ip._bd_tcl += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}] [get_bd_intf_pins {self.ip.hier_name}/{port_name}]\n"


class ExternalPort(Port):
    """Top-level port"""

    def __init__(self, design, name, protocol, direction, width=None):
        super().__init__(name, protocol, direction, width)
        self.design = design

    @property
    def hier_name(self):
        return f"{self.name}"


class ExternalPortRegular(ExternalPort):
    """Top-level regular port"""

    def __init__(self, design, name, protocol, direction, width):
        super().__init__(design, name, protocol, direction)
        self.width = width
        design._bd_tcl += f"create_bd_port -dir {self.direction} -from {self.width-1} -to 0 {self.name}\n"

    def connect(self, port):
        """Connect this port to an IP port(s)"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, IpPortRegular), type(port)
        self.design._bd_tcl += (
            f"connect_bd_net [get_bd_pins {self.name}] [get_bd_pins {port.hier_name}]\n"
        )
        port.connected = True


class ExternalPortInterface(ExternalPort):
    """Top level interface port"""

    def __init__(self, design, name, protocol, direction, properties=None):
        super().__init__(design, name, protocol, direction)
        design._bd_tcl += f"create_bd_intf_port -mode {self.direction} -vlnv {self.protocol} {self.name}\n"
        if properties:
            prop = ""
            for key in sorted(properties.keys()):
                prop += f"{key} {properties[key]} "

            design._bd_tcl += (
                f'set_property -dict "{prop}" [get_bd_intf_ports {self.hier_name}]\n'
            )

    def connect(self, port):
        """Connect this port to an IP port"""
        assert isinstance(port, IpPortInterface)
        self.design._bd_tcl += f"connect_bd_intf_net [get_bd_intf_pins {self.name}] [get_bd_intf_pins {port.hier_name}]\n"
        port.connected = True
