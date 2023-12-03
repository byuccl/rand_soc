""" IP class """

import abc
import logging
import pathlib
from pprint import pformat
import random

import yaml

from ..utils import all_ones, randintwidth

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
        for key in sorted(properties.keys()):
            prop += f"{key} {properties[key]} "

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

        yaml_path = pathlib.Path(module_path).with_suffix(".yaml")

        # self.config = {}
        self.config_vars = {}
        self.config_vars["all_ones"] = all_ones
        self.config_vars["randintwidth"] = randintwidth

        with open(yaml_path, "r") as f:
            ip_data = yaml.safe_load(f)

        self.data = {}
        for ip_yaml in ip_data:
            # Create entry for this IP
            ip = {}
            self.data[ip_yaml["id"]] = ip

            ip["definition"] = ip_yaml["definition"]

            config = {}
            ip["configuration"] = config
            for item in ip_yaml["configuration"]:
                name = item["name"]

                if "enable" in item:
                    if not eval(item["enable"], None, self.config_vars):
                        # print("Skipping")
                        continue

                config_item = {}
                assert name not in config, f"Duplicate config name: {name}"
                config[name] = config_item

                # Determine whether this configuration is used internally,
                # or whether it should be used to configure the IP in vivado
                if "internal" in item:
                    internal = item["internal"]
                    assert isinstance(internal, bool)
                else:
                    internal = False
                config_item["internal"] = internal

                if "value" in item:
                    value = item["value"]

                elif "values" in item:
                    values = item["values"]
                    assert isinstance(
                        values, list
                    ), f"values of {name} must be a list: {values}"
                    value = random.choice(values)

                elif "values_eval" in item:
                    values = item["values_eval"]
                    if isinstance(values, list):
                        # If a list, evaluate each item
                        try:
                            values = [
                                eval(value, None, self.config_vars) for value in values
                            ]
                        except TypeError as exc:
                            print(f"All arguments of {values} must be strings")
                            raise exc
                        except NameError as exc:
                            print(f"Error evaluting {values}")
                            raise exc
                    elif isinstance(values, str):
                        # If the value is a string, then it must be an expression that
                        # generates a list.  Evalute it.
                        values = eval(values, None, self.config_vars)
                    else:
                        raise NotImplementedError(
                            f"values of {name} must be a list or string: {values}"
                        )
                    value = random.choice(values)
                else:
                    raise NotImplementedError(f"{item} must have a value or values")

                if "format" in item:
                    format = item["format"]
                    if format == "hex":
                        value = hex(value)
                    else:
                        raise NotImplementedError(f"format {format} not supported")

                config_item["value"] = value
                self.config_vars[name] = value

                # print(f"self.config: {self.config}")
                # print(f"self.config_vars: {self.config_vars}")

            ports = {}
            ip["ports"] = ports
            for item in ip_yaml["ports"]:
                if "enable" in item:
                    if not eval(item["enable"], None, self.config_vars):
                        continue

                port = {}
                ports[item["name"]] = port
                port["protocol"] = item["protocol"]
                port["direction"] = item["direction"]
                port["connections"] = item["connections"]
                if "width" in item:
                    port["width"] = item["width"]

        logging.info("%s randomized to:\n%s", self.hier_name, pformat(self.data))
