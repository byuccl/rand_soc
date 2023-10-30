import argparse
import logging
import pathlib

import boolean

import spydrnet as sdn
from bfasst.utils.general import convert_verilog_literal_to_int
from bfasst.utils.sdn_helpers import SdnNetlistWrapper

from bfasst import jpype_jvm

jpype_jvm.start()
from com.xilinx.rapidwright.design.tools import LUTTools


# from gmt_tools.sop_eqn import SopEqn


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
        self.top = netlist_ir.top_instance

        for library in netlist_ir.get_libraries():
            if library.name == "hdi_primitives":
                self.library_hdi_primitives = library

        # Constant generator LUTs
        netlist_wrapper = SdnNetlistWrapper(self.top)
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
                self.top.reference.remove_child(instance_wrapper.instance)

        # Next split all LUT6_2s into logical LUTs
        netlist_wrapper = SdnNetlistWrapper(self.top)
        for instance_wrapper in netlist_wrapper.instances:
            if instance_wrapper.instance.reference.name != "LUT6_2":
                continue

            logging.info("=" * 80)
            logging.info("Creating logical LUT(s) for LUT6_2 instance: %s" % instance_wrapper.name)
            o6_pin_wrapper = instance_wrapper.get_pin("O6")
            o6_wire = o6_pin_wrapper.pin.wire
            assert o6_wire
            o6_net = netlist_wrapper.wire_to_net[o6_wire]
            assert o6_net
            o6_net_connected = o6_net.is_connected

            o5_pin_wrapper = instance_wrapper.get_pin("O5")
            o5_wire = o5_pin_wrapper.pin.wire
            assert o5_wire
            o5_net = netlist_wrapper.wire_to_net[o5_wire]
            assert o5_net
            o5_net_connected = o5_net.is_connected

            assert o6_net_connected or o5_net_connected

            # Get equation for LUT outputs
            eqn = LUTTools.getLUTEquation(instance_wrapper.properties["INIT"])[2:].replace("!", "~")
            eqn = boolean.BooleanAlgebra().parse(eqn)

            if o6_net_connected and o5_net_connected:
                o5_eqn = eqn.subs({boolean.Symbol("I5"): eqn.FALSE}).simplify()
                self.create_new_lut(o5_eqn, instance_wrapper, name=instance_wrapper.name + "O5")

                o6_eqn = eqn.subs({boolean.Symbol("I5"): eqn.TRUE}).simplify()
                self.create_new_lut(o6_eqn, instance_wrapper, name=instance_wrapper.name + "O6")

            elif o6_net_connected and not o5_net_connected:
                name = instance_wrapper.name
                instance_wrapper.instance.name = instance_wrapper.instance.name + ".OLD"
                self.create_new_lut(eqn, instance_wrapper, name=name)
            else:
                raise NotImplementedError

        # Write out netlist
        sdn.compose(netlist_ir, self.netlist_out, write_blackbox=False)

    def create_new_lut(self, eqn, old_instance_wrapper, name):
        num_inputs = len(eqn.symbols)
        logging.info("Creating new LUT %s with %d inputs" % (name, num_inputs))

        try:
            defn = next(
                d for d in self.library_hdi_primitives.definitions if d.name == "LUT%d" % num_inputs
            )
        except StopIteration:
            defn = self.library_hdi_primitives.create_definition(name="LUT%d" % num_inputs)

        logging.info("  equation: %s" % eqn)

        # Replace constant inputs in equation
        inputs = eqn.symbols
        for lut_input in inputs:
            pin_wrapper = old_instance_wrapper.get_pin(str(lut_input))

            if pin_wrapper.net.is_vdd:
                eqn = eqn.subs({lut_input: eqn.TRUE}).simplify()
            elif pin_wrapper.net.is_gnd:
                eqn = eqn.subs({lut_input: eqn.FALSE}).simplify()
        logging.info("  equation after constant inputs: %s" % eqn)

        mapping = {}
        logical_idx = 0
        for symbol in eqn.symbols:
            mapping[symbol] = boolean.Symbol("I%d" % logical_idx)
            logical_idx += 1
        logging.info(
            "  physical to logical mapping: %s" % {str(k): str(v) for k, v in mapping.items()}
        )

        eqn = eqn.subs(mapping).simplify()
        logging.info("  equation after mapping: %s" % eqn)

        eqn = str(eqn)
        eqn = eqn.replace("~", "!")
        eqn = eqn.replace("|", "+")
        eqn = "O=" + eqn
        init = str(LUTTools.getLUTInitFromEquation(eqn, num_inputs))
        logging.info("  INIT: %s" % init)

        instance = self.top.reference.create_child(
            name, reference=defn, properties={"VERILOG.Parameters": {"INIT": init}}
        )

        # Wire up the inputs
        for logical, physical in mapping.items():
            pin_wrapper = old_instance_wrapper.get_pin(str(physical))
            pin_wrapper.pin.wire.connect_pin(instance.get_pin(str(logical)).pin)

        return instance


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_path", type=pathlib.Path, help="Path to build directory")
    parser.add_argument("netlist_in", type=pathlib.Path, help="Path to input netlist")
    parser.add_argument("netlist_out", type=pathlib.Path, help="Path to output netlist")
    args = parser.parse_args()

    netlist_cleaner = NetlistPhysToLogical(args.build_path, args.netlist_in, args.netlist_out)
