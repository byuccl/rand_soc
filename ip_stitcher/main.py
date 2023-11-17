import jinja2

from ip_stitcher.microblaze import Microblaze


def main():
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

    project_config = {"part": "xc7a200tsbg484-1", "bd_name": "design_1"}

    template = env.get_template("run.tcl.j2")

    out = template.render(project_config)

    microblaze = Microblaze("ip_0")
    modules = [microblaze]

    for module in modules:
        module.instance()

    for module in modules:
        out += module.instance_str

    # Write the template to a file
    with open("run.tcl", "w", encoding="utf-8") as f:
        f.write(out)


if __name__ == "__main__":
    main()
