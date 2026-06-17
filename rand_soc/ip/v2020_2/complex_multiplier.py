"""Complex Multiplier IP"""

from ..ip_base import IPrandom


class ComplexMultiplier(IPrandom):
    """Complex Multiplier IP class"""

    @property
    def name(self):
        return "complex_multiplier"

    def randomize(self):
        self.load_data_from_yaml(__file__)
