""" AXI CAN IP """

from .ip_base import IPrandom


class AxiCan(IPrandom):
    """AXI CAN IP class"""

    @property
    def name(self):
        return "axi_can"

    def randomize(self):
        self.load_data_from_yaml(__file__)
