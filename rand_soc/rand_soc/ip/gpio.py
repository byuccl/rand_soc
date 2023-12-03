""" GPIO IP """

import random

from ..ports import Port
from .ip_base import IPrandom
from ..utils import all_ones, randbool, randintwidth


class Gpio(IPrandom):
    """GPIO IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)
        # self.config_dir = None
        # self.config_width = None
        # self.config_default_out_val = None
        # self.config_default_tristate_val = None
        # self.config_dual_channel = None
        # self.config_dir2 = None
        # self.config_width2 = None
        # self.config_default_out_val2 = None
        # self.config_default_tristate_val2 = None

    @property
    def name(self):
        return "gpio"

    def instance(self):
        super().instance()

        print(self.data)
        for ip_id, ip_props in self.data.items():
            ip_config = {
                f"CONFIG.{config_name}": config_props["value"]
                for config_name, config_props in ip_props["configuration"].items()
                if not config_props["internal"]
            }
            self._new_instance(ip_props["definition"], ip_id, ip_config)

            for port_name, port_props in ip_props["ports"].items():
                self._create_hier_pin(
                    port_name,
                    port_props["protocol"],
                    port_props["direction"],
                    port_props.get("width"),
                ).connect_internal(port_props["connections"])

    def randomize(self):
        super().randomize(__file__)

        # self.config_dir = "IO"  # random.choice(["I", "O", "IO"])
        # self.config_width = random.randint(1, 32)
        # if self.config_dir in ("O", "IO"):
        #     self.config_default_out_val = random.choice(
        #         (0, all_ones(self.config_width), randintwidth(self.config_width))
        #     )
        # if self.config_dir in ("IO",):
        #     self.config_default_tristate_val = random.choice(
        #         (0, all_ones(self.config_width), randintwidth(self.config_width))
        #     )

        # self.config_dual_channel = randbool()
        # if self.config_dual_channel:
        #     self.config_dir2 = random.choice(["I", "O", "IO"])
        #     self.config_width2 = random.randint(1, 32)
        #     if self.config_dir2 in ("O", "IO"):
        #         self.config_default_out_val2 = random.choice(
        #             (0, all_ones(self.config_width2), randintwidth(self.config_width2))
        #         )
        #     if self.config_dir2 in ("IO",):
        #         self.config_default_tristate_val2 = random.choice(
        #             (0, all_ones(self.config_width2), randintwidth(self.config_width2))
        #         )
        # self.config_interrupt_enabled = randbool()
