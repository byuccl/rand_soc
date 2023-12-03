""" GPIO IP """

import random

from ..ports import Port
from .ip_base import IPrandom
from ..utils import all_ones, randbool, randintwidth


class Gpio(IPrandom):
    """GPIO IP class"""

    def __init__(self, design, name):
        super().__init__(design, name)

    @property
    def name(self):
        return "gpio"

    def randomize(self):
        self.load_data_from_yaml(__file__)

    def instance(self):
        super().instance()
        self.instance_using_yaml_data()
    
