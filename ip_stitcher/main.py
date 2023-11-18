from ip_stitcher.creator import DesignCreator


def main():
    c = DesignCreator()

    c.run()

    # Write the template to a file
    with open("run.tcl", "w", encoding="utf-8") as f:
        f.write(c.project_tcl_str)


if __name__ == "__main__":
    main()
