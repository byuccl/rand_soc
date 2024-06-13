""" GPIO IP """

from .ip_base import IPrandom


class Gpio(IPrandom):
    """GPIO IP class"""

    @property
    def name(self):
        return "gpio"

    def randomize(self):
        self.load_data_from_yaml(__file__)

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()
