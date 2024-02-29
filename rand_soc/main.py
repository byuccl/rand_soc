import argparse
import pathlib
from random import randint

from rand_soc.creator import RandomDesign


def main(output_dir_path, seed=None, part=None):
    design = RandomDesign(output_dir_path, seed=seed, part=part)
    design.create()
    design.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir_path", type=pathlib.Path, help="Output directory path")
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--part", type=str)
    args = parser.parse_args()

    main(args.output_dir_path, args.seed, args.part)
