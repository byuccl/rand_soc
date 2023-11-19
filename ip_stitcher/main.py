import pathlib

from ip_stitcher.creator import DesignCreator


def main():
    c = DesignCreator()

    c.run(output_dir_path=pathlib.Path("designs"), num_designs=10)


if __name__ == "__main__":
    main()
