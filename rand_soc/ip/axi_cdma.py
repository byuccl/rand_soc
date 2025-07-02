""" AXI CDMA IP """

from .ip_base import IPrandom


class AxiCdma(IPrandom):
    """AXI CDMA IP class"""

    @property
    def name(self):
        return "axi_cdma"

    def randomize(self):
        self.load_data_from_yaml(__file__)
