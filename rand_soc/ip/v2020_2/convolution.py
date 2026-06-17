"""Convolution Encoder IP"""

from ..ip_base import IPrandom


class ConvolutionEncoder(IPrandom):
    """Convolution Encoder IP class"""

    @property
    def name(self):
        return "conv_encoder"

    def randomize(self):
        self.load_data_from_yaml(__file__)
