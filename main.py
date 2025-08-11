import argparse
import pathlib
from random import randint

from rand_soc.creator import RandomDesign


def main(output_dir_path, config_path=None, seed=None, part=None):
    design = RandomDesign(
        output_dir_path, config_path=config_path, seed=seed, part=part
    )
    design.create()
    design.write()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output_dir_path", type=pathlib.Path, help="Output directory path"
    )
    parser.add_argument(
        "config_path", type=pathlib.Path, help="Path of rand_soc creator yaml"
    )
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--part", type=str, help="Xilinx part name")
    args = parser.parse_args()

    main(args.output_dir_path, args.config_path, args.seed, args.part)
