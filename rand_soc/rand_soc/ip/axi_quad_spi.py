""" AXI Quad SPI IP """

from .ip_base import IPrandom


class AxiQuadSpi(IPrandom):
    """AXI Quad SPI IP class"""

    @property
    def name(self):
        return "axi_quad_spi"

    def randomize(self):
        self.load_data_from_yaml(__file__)
