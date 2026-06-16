"""AXI DMA IP"""

from ..ip_base import IPrandom


class AxiDma(IPrandom):
    """AXI DMA IP class"""

    @property
    def name(self):
        return "axi_dma"

    def randomize(self):
        self.load_data_from_yaml(__file__)
