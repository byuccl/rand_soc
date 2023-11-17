""" IP class """


import abc


class IP:
    """Base class for IP"""

    def __init__(self):
        self.hier_name = None
        self.instance_str = "\n\n" + "#" * 10 + " " + self.name + " " + "#" * 10 + "\n"

    @abc.abstractmethod
    def instance():
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name():
        raise NotImplementedError

    def new_instance(self, ip_name, instance_name):
        self.instance_str += (
            f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        )
        self.instance_str += f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"

    # def move_to_hier(self, instance_name):
    #     return f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"
