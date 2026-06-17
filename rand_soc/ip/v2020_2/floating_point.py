"""Floating-Point Operator IP"""

from ..ip_base import IPrandom


class FloatingPoint(IPrandom):
    """Floating-Point Operator IP class"""

    @property
    def name(self):
        return "floating_point"

    def randomize(self):
        self.load_data_from_yaml(__file__)
