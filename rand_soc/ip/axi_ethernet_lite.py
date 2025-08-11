""" AXI EthernetLite IP """

from .ip_base import IPrandom


class AxiEthernetLite(IPrandom):
    """AXI EthernetLite IP class"""

    @property
    def name(self):
        return "axi_ethernet_lite"

    def randomize(self):
        self.load_data_from_yaml(__file__)
