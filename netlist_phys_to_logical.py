import argparse
import logging
import pathlib

import spydrnet as sdn
from bfasst.utils.general import convert_verilog_literal_to_int
from bfasst.utils.sdn_helpers import SdnNetlistWrapper


class NetlistPhysToLogical:
    def __init__(self, build_path, netlist_in_path, netlist_out_path):
        self.build_path = build_path
        self.netlist_in = netlist_in_path
        self.netlist_out = netlist_out_path

        self.log_path = self.build_path / "log.txt"
        self.log_path.unlink(missing_ok=True)

        logging.basicConfig(
            filename=self.log_path,
            format="%(asctime)s %(message)s",
            level=logging.DEBUG,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Read netlist with spydrnet
        netlist_ir = sdn.parse(self.netlist_in)
        top = netlist_ir.top_instance

        # Constant generator LUTs
        netlist_wrapper = SdnNetlistWrapper(top)
        for instance_wrapper in netlist_wrapper.instances:
            if instance_wrapper.instance.reference.name != "LUT6_2":
                continue
            init = instance_wrapper.properties["INIT"]
            init_int = convert_verilog_literal_to_int(init)

            # Not sure we ever see a constant-1 generator LUT
            assert init_int != 0xFFFFFFFFFFFFFFFF, "Found a LUT with INIT=FFFFFFFFFFFFFFFF"

            if init_int == 0:
                logging.info("Removing instance: %s", instance_wrapper.name)
                raise NotImplementedError

            # print("INIT value:", init_int)

        # Write out netlist
        sdn.compose(netlist_ir, self.netlist_out, write_blackbox=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=pathlib.Path, help="Path to build directory")
    parser.add_argument("netlist_in", type=pathlib.Path, help="Path to input netlist")
    parser.add_argument("netlist_out", type=pathlib.Path, help="Path to output netlist")
    args = parser.parse_args()

    netlist_cleaner = NetlistPhysToLogical(args.build_path, args.netlist_in, args.netlist_out)
