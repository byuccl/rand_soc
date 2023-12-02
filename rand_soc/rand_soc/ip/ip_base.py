""" IP class """

import abc

from ..ports import IpPortInterface, IpPortRegular


class IP:
    """Base class for IP"""

    def __init__(self, design, name):
        self.design = design
        self.hier_name = name + "_" + self.name
        self._bd_tcl = f"\n\n########## {self.name} ##########\n"
        self.ports = []

    def instance(self):
        """Generate Tcl to instance the IP"""
        self._bd_tcl += f"create_bd_cell -type hier {self.hier_name}\n"

    @property
    @abc.abstractmethod
    def name(self):
        """Get the name of the IP (type not instance)"""
        raise NotImplementedError

    def _new_instance(self, ip_name, instance_name, properties=None):
        """Create a new instance of an IP"""
        self._bd_tcl += f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        self._bd_tcl += f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        # Combine key, value pairs into a single string
        prop = ""
        for key, value in properties.items():
            prop += f"{key} {value} "
        self._bd_tcl += f'set_property -dict "{prop}" [get_bd_cells {self.hier_name}/{instance_name}]\n'

    def _create_hier_pin(
        self, name, protocol, direction, width=None, addr_seg_name=None
    ):
        if protocol.startswith("xilinx.com:"):
            port = IpPortInterface(self, name, protocol, direction, addr_seg_name)
        else:
            port = IpPortRegular(self, name, protocol, direction, width)
        return port

    def _connect_internal_pins_interface(self, instance_pin_a, instance_pin_b):
        self._bd_tcl += f"connect_bd_intf_net [get_bd_intf_pins {self.hier_name}/{instance_pin_a}] [get_bd_intf_pins {self.hier_name}/{instance_pin_b}]\n"

    def _connect_internal_pins_regular(self, instance_pin_a, instance_pin_b):
        self._bd_tcl += f"connect_bd_net [get_bd_pins {self.hier_name}/{instance_pin_a}] [get_bd_pins {self.hier_name}/{instance_pin_b}]\n"

    def _assign_bd_address(self, instance_addr_space_name, slave_name):
        self._bd_tcl += f"assign_bd_address -target_address_space /{self.hier_name}/{instance_addr_space_name} [get_bd_addr_segs {self.hier_name}/{slave_name}] -force\n"

    @property
    def bd_str(self):
        """Get the Tcl string to create the IP"""
        return self._bd_tcl


class IPrandom(IP):
    """IP class with randomization"""

    @abc.abstractmethod
    def randomize(self):
        """Randomize the IP"""
        raise NotImplementedError

    def randomize(self, module_path):
        # Read the component.xml file

        yaml_path = pathlib.Path(__file__).with_suffix(".yaml")

        self.config = {}
        with open(yaml_path, "r") as f:
            options = yaml.safe_load(f)

        for config in options["Configuration"]:
            print("")
            print(config)

            if "enable" in config:
                if not eval(config["enable"], None, self.config):
                    print("Skipping")
                    continue

            if isinstance(config["values"], list):
                # If the value is a list, do nothing
                vals = config["values"]
            elif isinstance(config["values"], str):
                # If the value is a string, then it must be an expression that
                # generates a list.  Evalute it.
                vals = eval(config["values"])
                print(vals)

            choice = random.choice(vals)
            print(choice)
            self.config[f"{config['name']}"] = choice

            print(self.config)

        raise NotImplementedError
