""" AXI IIC IP """

from .ip_base import IPrandom


class AxiIic(IPrandom):
    """AXI IIC IP class"""

    @property
    def name(self):
        return "axi_iic"

    def randomize(self):
        self.load_data_from_yaml(__file__)
