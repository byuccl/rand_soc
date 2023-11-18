""" IP class """


import abc


class IP:
    """Base class for IP"""

    def __init__(self):
        self.hier_name = None
        self.instance_str = f"\n\n########## {self.name} ##########\n"
        self.clk_inputs = []
        self.reset_inputs = []
        self.interrupt_inputs = []

    @abc.abstractmethod
    def instance():
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name():
        raise NotImplementedError

    def new_instance(self, ip_name, instance_name, properties=None):
        self.instance_str += (
            f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        )
        self.instance_str += f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        for prop, value in properties.items():
            self.instance_str += f'set_property -dict "{prop} {value}" [get_bd_cells {self.hier_name}/{instance_name}]\n'

    def create_hier_pin(self, direction, name):
        self.instance_str += f"create_bd_pin -dir {direction} {self.hier_name}/{name}\n"

    def connect_bd_pin(self, hier_pin, instance_pin):
        self.instance_str += f"connect_bd_net [get_bd_pins {self.hier_name}/{hier_pin}] [get_bd_pins {self.hier_name}/{instance_pin}]\n"

    def connect_instance_pin(self, instance_pin_a, instance_pin_b):
        self.instance_str += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{instance_pin_a}] [get_bd_intf_pins {self.hier_name}/{instance_pin_b}]\n"
