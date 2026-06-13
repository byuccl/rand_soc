"""FFT IP"""

from ..ip_base import IPrandom


class Fft(IPrandom):
    """FFT IP class"""

    @property
    def name(self):
        return "fft"

    def randomize(self):
        self.load_data_from_yaml(__file__)
