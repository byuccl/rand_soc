""" AXI HWICAP IP """

from .ip_base import IPrandom


class AxiHwicap(IPrandom):
    """AXI HWICAP IP class"""


    @property
    def name(self):
        return "axi_hwicap"

    def randomize(self):
        self.load_data_from_yaml(__file__)

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()