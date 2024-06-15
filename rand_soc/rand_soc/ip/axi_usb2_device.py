""" AXI USB2 DEVICE IP """

from .ip_base import IPrandom


class AxiUsb2Device(IPrandom):
    """AXI USB2 DEVICE IP class"""

    @property
    def name(self):
        return "axi_usb2_device"

    def randomize(self):
        self.load_data_from_yaml(__file__)
