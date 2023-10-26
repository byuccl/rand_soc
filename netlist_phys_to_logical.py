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

        # Get const0
        # const0 = [wire for wire in top.get_wires() if wire.cable.name == r"\<const0>"]
        # assert len(const0) == 1
        # const0 = const0[0]

        # Constant generator LUTs
        netlist_wrapper = SdnNetlistWrapper(top)
        const0 = netlist_wrapper.get_const0_wire()
        for instance_wrapper in netlist_wrapper.instances:
            if instance_wrapper.instance.reference.name != "LUT6_2":
                continue
            init = instance_wrapper.properties["INIT"]
            init_int = convert_verilog_literal_to_int(init)

            # Not sure we ever see a constant-1 generator LUT
            assert init_int != 0xFFFFFFFFFFFFFFFF, "Found a LUT with INIT=FFFFFFFFFFFFFFFF"

            if init_int == 0:
                logging.info("")
                logging.info(
                    "Processing constant-0 generator LUT instance: %s", instance_wrapper.name
                )

                pin_wrapper = instance_wrapper.get_pin("I0")

                outputs = ("O5", "O6")

                for output in outputs:
                    pin_wrapper = instance_wrapper.get_pin(output)
                    assert pin_wrapper

                    wire = pin_wrapper.pin.wire
                    assert wire

                    pins_to_remove = []
                    for pin2 in wire.pins:
                        if pin2 == pin_wrapper.pin:
                            continue
                        pins_to_remove.append(pin2)

                    for pin2 in pins_to_remove:
                        logging.info(
                            "Disconnecting wire %s from %s.%s[%d]",
                            pin2.wire.cable.name,
                            pin2.instance.name,
                            pin2.inner_pin.port.name,
                            pin2.inner_pin.port.pins.index(pin2.inner_pin),
                        )
                        wire.disconnect_pin(pin2)

                        logging.info(
                            r"Connecting \<const0> to %s.%s[%d]",
                            pin2.instance.name,
                            pin2.inner_pin.port.name,
                            pin2.inner_pin.port.pins.index(pin2.inner_pin),
                        )
                        const0.connect_pin(pin2)

                logging.info("Removing instance: %s", instance_wrapper.name)
                top.reference.remove_child(instance_wrapper.instance)

        # Write out netlist
        sdn.compose(netlist_ir, self.netlist_out, write_blackbox=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=pathlib.Path, help="Path to build directory")
    parser.add_argument("netlist_in", type=pathlib.Path, help="Path to input netlist")
    parser.add_argument("netlist_out", type=pathlib.Path, help="Path to output netlist")
    args = parser.parse_args()

    netlist_cleaner = NetlistPhysToLogical(args.build_path, args.netlist_in, args.netlist_out)
