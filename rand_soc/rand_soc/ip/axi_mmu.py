""" AXI MMU IP """

from .ip_base import IPrandom


class Gpio(IPrandom):
    """AXI MMU IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)

    @property
    def name(self):
        return "axi_mmu"

    def randomize(self):
        self.load_data_from_yaml(__file__)

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()
