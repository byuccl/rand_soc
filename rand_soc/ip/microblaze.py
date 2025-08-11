""" MICROBLAZE IP """

from .ip_base import IPrandom


class Microblaze(IPrandom):
    """MICROBLAZE IP class"""

    @property
    def name(self):
        return "microblaze"

    def randomize(self):
        self.load_data_from_yaml(__file__)
