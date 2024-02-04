""" Accumulator IP """

from .ip_base import IPrandom


class Accumulator(IPrandom):
    """Accumulator IP class"""

    @property
    def name(self):
        return "accumulator"

    def randomize(self):
        return self.load_data_from_yaml(__file__)

    def instance(self):
        super().instance()

        self.instance_using_yaml_data()
