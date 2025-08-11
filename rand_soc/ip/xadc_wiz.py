""" XADC WIZARD IP """

from .ip_base import IPrandom


class XadcWiz(IPrandom):
    """XADC WIZARD IP class"""

    @property
    def name(self):
        return "xadc_wiz"

    def randomize(self):
        self.load_data_from_yaml(__file__)
