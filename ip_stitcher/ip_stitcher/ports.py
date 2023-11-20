class Port:
    """A port on an IP, either external or internal"""

    def __init__(
        self,
        name,
        direction=None,
        width=None,
        protocol=None,
        mode=None,
        ip=None,
        addr_seg_name=None,
    ):
        self.ip = ip
        self.name = name
        self.direction = direction
        self.width = width
        self.protocol = protocol
        self.mode = mode
        self.addr_seg_name = addr_seg_name

    @property
    def hier_name(self):
        """Return the hierarchical name of the port"""
        if self.ip:
            return f"{self.ip.hier_name}/{self.name}"
        else:
            return self.name

    def __repr__(self):
        return f"Port({self.ip.name}, {self.name}, {self.direction}, {self.width}, {self.protocol}, {self.mode})"
