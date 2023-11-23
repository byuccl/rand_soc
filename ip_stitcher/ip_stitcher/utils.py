import random


def randbool():
    return random.choice([True, False])


def randintwidth(width):
    return random.randint(0, 2**width - 1)


def all_ones(width):
    return 2**width - 1


def pull_from_list(lst, new_list, fcn):
    lst_copy = []
    for item in lst:
        (new_list if fcn(item) else lst_copy).append(item)
    lst[:] = lst_copy
