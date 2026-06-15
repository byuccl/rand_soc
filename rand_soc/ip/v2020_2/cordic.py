"""CORDIC IP"""

from ..ip_base import IPrandom


class Cordic(IPrandom):
    """CORDIC IP class"""

    @property
    def name(self):
        return "cordic"

    def randomize(self):
        self.load_data_from_yaml(__file__)
