""" IP class """


import abc


class IP:
    """Base class for IP"""

    def __init__(self, name):
        self.hier_name = name + "_" + self.name
        self.instance_str = f"\n\n########## {self.name} ##########\n"
        self.ports = []

    @abc.abstractmethod
    def instance(self):
        """Generate Tcl to instance the IP"""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name(self):
        """Get the name of the IP (type not instance)"""
        raise NotImplementedError

    @abc.abstractmethod
    def randomize(self):
        """Randomize the IP"""
        raise NotImplementedError

    def _new_instance(self, ip_name, instance_name, properties=None):
        """Create a new instance of an IP"""
        self.instance_str += (
            f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        )
        self.instance_str += f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        # Combine key, value pairs into a single string
        prop = ""
        for key, value in properties.items():
            prop += f"{key} {value} "
        self.instance_str += f'set_property -dict "{prop}" [get_bd_cells {self.hier_name}/{instance_name}]\n'

    def _create_hier_pin(self, port, connect_to_pins=None):
        """Create a hierarchical pin"""
        if port.protocol.startswith("xilinx.com:interface:"):
            self.instance_str += f"create_bd_intf_pin -mode {port.mode} -vlnv {port.protocol} {self.hier_name}/{port.name}\n"
        else:
            self.instance_str += f"create_bd_pin -dir {port.direction} -from {port.width-1} -to 0 {self.hier_name}/{port.name}\n"
        self.ports.append(port)

        if connect_to_pins:
            for pin in connect_to_pins:
                self._connect_bd_pin(port, pin)

    def _connect_bd_pin(self, port, instance_pin):
        """Connect a hierarchical pin to another hierarchical pin"""
        if port.protocol.startswith("xilinx.com:interface:"):
            self.instance_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{port.name}] [get_bd_intf_pins {self.hier_name}/{instance_pin}]\n"
        else:
            self.instance_str += f"connect_bd_net [get_bd_pins {self.hier_name}/{port.name}] [get_bd_pins {self.hier_name}/{instance_pin}]\n"

    def _connect_instance_pin(self, instance_pin_a, instance_pin_b):
        self.instance_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{instance_pin_a}] [get_bd_intf_pins {self.hier_name}/{instance_pin_b}]\n"

    def _assign_bd_address(self, instance_addr_space_name, slave_name):
        self.instance_str += f"assign_bd_address -target_address_space /{self.hier_name}/{instance_addr_space_name} [get_bd_addr_segs {self.hier_name}/{slave_name}] -force\n"
