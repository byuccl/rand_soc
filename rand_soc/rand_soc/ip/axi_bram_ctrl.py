""" AXI BRAM Controller """

from .ip_base import IPrandom


class AxiBRAMCtrl(IPrandom):
    """AXI BRAM Controller IP class"""

    @property
    def name(self):
        return "axi_bram_ctrl"

    def randomize(self):
        self.load_data_from_yaml(__file__)
