""" Discrete Fourier Transform IP """

from .ip_base import IPrandom


class Dft(IPrandom):
    """Discrete Fourier Transform IP class"""

    @property
    def name(self):
        return "dft"

    def randomize(self):
        self.load_data_from_yaml(__file__)
