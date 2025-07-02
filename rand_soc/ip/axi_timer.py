""" AXI TIMER IP """

from .ip_base import IPrandom


class AxiTimer(IPrandom):
    """AXI TIMER IP class"""

    @property
    def name(self):
        return "axi_timer"

    def randomize(self):
        self.load_data_from_yaml(__file__)
