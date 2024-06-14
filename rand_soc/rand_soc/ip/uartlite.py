""" UARTLite IP """

from .ip_base import IPrandom


class Uartlite(IPrandom):
    """UARTLite IP class"""

    @property
    def name(self):
        return "uartlite"

    def randomize(self):
        self.load_data_from_yaml(__file__)
