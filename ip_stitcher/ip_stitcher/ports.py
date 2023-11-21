import abc


class Port:
    """A port on an IP, either external or internal"""

    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        name,
        protocol,
        direction
        # direction=None,
        # width=None,
        # protocol=None,
        # mode=None,
        # ip=None,
        # addr_seg_name=None,
    ):
        # self.ip = ip
        self.name = name
        self.direction = direction
        # self.width = width
        self.protocol = protocol
        # self.mode = mode
        # self.addr_seg_name = addr_seg_name
        self.connected = False

    # @property
    # def hier_name(self):
    #     """Return the hierarchical name of the port"""
    #     if self.ip:
    #         return f"{self.ip.hier_name}/{self.name}"
    #     else:
    #         return self.name

    # def __repr__(self):
    #     return f"Port({self.ip.name}, {self.name}, {self.direction}, {self.width}, {self.protocol}, {self.mode})"

    # @abc.abstractmethod
    # def create_str(self):
    #     raise NotImplementedError


class IpPort(Port):
    """IP Port"""

    def __init__(self, ip, name, protocol, direction):
        super().__init__(name, protocol, direction)
        self.ip = ip
        self.ip.ports.append(self)

    def hier_name(self):
        return f"{self.ip.hier_name}/{self.name}"


class IpPortRegular(IpPort):
    """IP regular port"""

    def __init__(self, ip, name, protocol, direction, width):
        super().__init__(ip, name, protocol, direction)
        self.width = width
        self.ip._bd_str += f"create_bd_pin -dir {self.direction} -from {self.width-1} -to 0 {self.hier_name()}\n"

    def __repr__(self) -> str:
        return f"IpPortRegular({self.hier_name()}, {self.direction}, {self.width}, {self.protocol})"

    def connect(self, port):
        """Connect this port to a top-level port, another IP port, or internal port (str)"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, (ExternalPortRegular, IpPortRegular, str))
        if isinstance(port, ExternalPortRegular):
            port.connect(self)
        elif isinstance(port, str):
            self.ip._bd_str += f"connect_bd_net [get_bd_pins {self.hier_name()}] [get_bd_pins {self.ip.hier_name}/{port}]\n"
        else:
            self.ip.design.ip_to_ip_connections_str += f"connect_bd_net [get_bd_pins {self.hier_name()}] [get_bd_pins {port.hier_name()}]\n"


class IpPortInterface(IpPort):
    """IP interface port"""

    def __init__(
        self,
        ip,
        name,
        protocol,
        direction,
        addr_seg_name=None,
    ):
        super().__init__(ip, name, protocol, direction)
        self.addr_seg_name = addr_seg_name
        self.ip._bd_str += f"create_bd_intf_pin -mode {self.direction} -vlnv {self.protocol} {self.hier_name()}\n"

    def __repr__(self) -> str:
        return f"IpPortInterface({self.hier_name()}, {self.direction}, {self.protocol}, {self.addr_seg_name})"

    def connect(self, port):
        """Connect this port to a top-level port, another IP port, or an internal pin (str)"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, (ExternalPortInterface, IpPortInterface, str))
        if isinstance(port, ExternalPortInterface):
            port.connect(self)
        elif isinstance(port, str):
            self.ip._bd_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name()}] [get_bd_intf_pins {self.ip.hier_name}/{port}]\n"
        else:
            self.ip.design.ip_to_ip_connections_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name()}] [get_bd_intf_pins {port.hier_name()}]\n"


class ExternalPort(Port):
    """Top-level port"""

    def __init__(self, design, name, protocol, direction):
        super().__init__(name, protocol, direction)
        self.design = design


class ExternalPortRegular(ExternalPort):
    """Top-level regular port"""

    def __init__(self, design, name, protocol, direction, width):
        super().__init__(design, name, protocol, direction)
        self.width = width
        design._bd_str += f"create_bd_port -dir {self.direction} -from {self.width-1} -to 0 {self.name}\n"

    def connect(self, port):
        """Connect this port to an IP port(s)"""
        if isinstance(port, (list, tuple)):
            for p in port:
                self.connect(p)
            return

        assert isinstance(port, IpPortRegular), type(port)
        self.design._bd_str += f"connect_bd_net [get_bd_pins {self.name}] [get_bd_pins {port.hier_name()}]\n"


class ExternalPortInterface(ExternalPort):
    """Top level interface port"""

    def __init__(self, design, name, protocol, direction):
        super().__init__(design, name, protocol, direction)
        design._bd_str += f"create_bd_intf_port -mode {self.direction} -vlnv {self.protocol} {self.name}\n"

    def connect(self, port):
        """Connect this port to an IP port"""
        assert isinstance(port, IpPortInterface)
        self.design._bd_str += f"connect_bd_intf_net [get_bd_intf_pins {self.name}] [get_bd_intf_pins {port.hier_name}]\n"
