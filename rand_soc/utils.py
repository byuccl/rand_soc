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


def divide_into_groups(num_items, num_groups):
    # Calculate the base size of each group
    base_size = num_items // num_groups
    remainder = num_items % num_groups

    groups = [base_size] * num_groups

    # Distribute the remainder across the first few groups
    for i in range(remainder):
        groups[i] += 1

    return groups
