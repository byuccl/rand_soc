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
        self._impl_constraints_tcl = ""
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
        self._bd_tcl += (
            f"move_bd_cells [get_bd_cells {self.hier_name}] [get_bd_cells {instance_name}]\n"
        )
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        # Combine key, value pairs into a single string
        prop = ""
        for key in sorted(properties.keys()):
            prop += f"{key} {properties[key]} "

        self._bd_tcl += (
            f'set_property -dict "{prop}" [get_bd_cells {self.hier_name}/{instance_name}]\n'
        )

    def _create_hier_pin(self, name, protocol, direction, width=None, addr_segs=None):
        if protocol.startswith("xilinx.com:"):
            port = IpPortInterface(self, name, protocol, direction, addr_segs)
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

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()

    def instance_using_yaml_data(self):
        """Instance an IP using the data read from its yaml file"""

        for ip_id, ip_props in self.data.items():
            ip_config = {
                f"CONFIG.{config_name}": config_props["value"]
                for config_name, config_props in ip_props["configuration"].items()
                if not config_props.get("internal")
            }
            self._new_instance(ip_props["definition"], ip_id, ip_config)

            if "internal_connections" in ip_props:
                self.instance_yaml_internal_connections(ip_props)

            if "ports" in ip_props:
                for port_name, port_props in ip_props["ports"].items():
                    self._create_hier_pin(
                        port_name,
                        port_props["protocol"],
                        port_props["direction"],
                        port_props.get("width"),
                        [f"{ip_id}/{a}" for a in port_props.get("addr_segs", [])],
                    ).connect_internal(port_props["connections"])

                    if "clk_pins" in port_props:
                        for clk_pin in port_props["clk_pins"]:
                            self._impl_constraints_tcl += f"set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {self.hier_name}_{port_name}_{clk_pin['name']}_{clk_pin['direction']}BUF]\n"

            if "address_segments" in ip_props:
                for address_segment in ip_props["address_segments"]:
                    pass
                    # self._assign_bd_address(
                    #     address_segment["master_name"],
                    #     ip_id + "/" + address_segment["slave_name"],
                    # )

    def instance_yaml_internal_connections(self, ip_props):
        """Helper method to connect internal wires within a group of IP"""

        for connection in ip_props["internal_connections"]:
            if "enable" in connection:
                if not eval(connection["enable"], None, self.config_vars):
                    continue

            f = connection["from"]
            t = connection["to"]

            if connection["is_interface"]:
                self._connect_internal_pins_interface(f, t)
            else:
                self._connect_internal_pins_regular(f, t)

    def load_data_from_yaml(self, module_path):
        """Read the <component>.yaml file"""

        yaml_path = pathlib.Path(module_path).with_suffix(".yaml")

        # self.config = {}
        self.config_vars = {}
        self.config_vars["all_ones"] = all_ones
        self.config_vars["randintwidth"] = randintwidth

        with open(yaml_path, "r") as f:
            ip_data = yaml.safe_load(f)

        self.data = {}
        for ip_yaml in ip_data:
            # Check if IP requires a satisfied condition before instancing
            if "enable" in ip_yaml:
                if not eval(ip_yaml["enable"], None, self.config_vars):
                    continue

            # Create entry for this IP
            ip = {}
            self.data[ip_yaml["id"]] = ip

            ip["definition"] = ip_yaml["definition"]

            config = {}
            ip["configuration"] = config
            for item in ip_yaml["configuration"]:
                name = item["name"]

                enabled = True
                if "enable" in item:
                    if not eval(item["enable"], None, self.config_vars):
                        enabled = False
                        if "default" not in item:
                            continue

                config_item = {}
                assert name not in config, f"Duplicate config name: {name}"
                config[name] = config_item

                # Determine whether this configuration is used internally,
                # or whether it should be used to configure the IP in vivado
                if "internal" in item:
                    internal = item["internal"]
                    assert isinstance(internal, bool)
                    config_item["internal"] = internal
                else:
                    internal = False

                if not enabled:
                    value = item["default"]

                elif "value" in item:
                    value = item["value"]

                elif "values" in item:
                    values = item["values"]
                    assert isinstance(values, list), f"values of {name} must be a list: {values}"
                    value = random.choice(values)

                elif "values_eval" in item:
                    try:
                        values = eval(item["values_eval"], None, self.config_vars)
                    except Exception as e:
                        print(f"Error evaluating {item['values_eval']} in {yaml_path}")
                        raise e
                    value = random.choice(values)
                else:
                    raise NotImplementedError(f"{item} must have a value or values")

                if isinstance(value, bool):
                    value = int(value)
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
            if "ports" in ip_yaml:
                self.load_ports_from_yaml(ip, ip_yaml)

            keys_to_copy = ["internal_connections", "address_segments"]
            for key in keys_to_copy:
                if key in ip_yaml:
                    ip[key] = ip_yaml[key]

        logging.info("%s randomized to:\n%s", self.hier_name, pformat(self.data))

    def load_ports_from_yaml(self, ip, ip_yaml):
        """Helper method to load IP port data from yaml into IP entry"""

        ports = {}
        ip["ports"] = ports
        for item in ip_yaml["ports"]:
            if "enable" in item and not eval(item["enable"], None, self.config_vars):
                continue

            port = {}
            ports[item["name"]] = port
            port["protocol"] = item["protocol"]
            port["direction"] = item["direction"]
            port["connections"] = item["connections"]
            if "width" in item:
                port["width"] = eval(str(item["width"]), None, self.config_vars)
            if "clk_pins" in item:
                port["clk_pins"] = item["clk_pins"]
            if "addr_segs" in item:
                port["addr_segs"] = []
                for addr_seg in item["addr_segs"]:
                    if (
                        "enable" in addr_seg and eval(addr_seg["enable"], None, self.config_vars)
                    ) or "enable" not in addr_seg:
                        port["addr_segs"].append(addr_seg["name"])
