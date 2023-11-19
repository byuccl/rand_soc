import random


def randbool():
    return random.choice([True, False])


def randintwidth(width):
    return random.randint(0, 2**width - 1)


def all_ones(width):
    return 2**width - 1
