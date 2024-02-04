""" UARTLite IP """

from .ip_base import IPrandom


class Uartlite(IPrandom):
    @property
    def name(self):
        return "uartlite"

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()

    def randomize(self):
        self.load_data_from_yaml(__file__)
