class Port:
    def __init__(self, name, dir=None, width=None, protocol=None, mode=None, ip=None):
        self.ip = ip
        self.name = name
        self.dir = dir
        self.width = width
        self.protocol = protocol
        self.mode = mode

    @property
    def hier_name(self):
        if self.ip:
            return f"{self.ip.hier_name}/{self.name}"
        else:
            return self.name

    def __repr__(self):
        return f"Port({self.ip.name}, {self.name}, {self.dir}, {self.width}, {self.protocol}, {self.mode})"
