from .ip_base import IP


class SliceAndConcat(IP):
    def __init__(self, design, name, drive_port, drivers):
        super().__init__(design, name)
        self.drive_port = drive_port
        self.drivers = drivers
        self.instance()

    @property
    def name(self):
        return "slice_and_concat"

    def instance(self):
        super().instance()
        port_out = self._create_hier_pin(
            "out0", self.drive_port.protocol, "O", self.drive_port.width
        )
        port_out.connect(self.drive_port)

        # Check if concat needs to be used
        if len(self.drivers) > 1:
            concat_used = True
            self._new_instance(
                "xilinx.com:ip:xlconcat:2.1",
                "concat",
                {"CONFIG.NUM_PORTS": len(self.drivers)},
            )
            port_out.connect_internal("concat/dout")
        else:
            concat_used = False

        for i, driver in enumerate(self.drivers):
            port, bit_high, bit_low = driver

            port_in = self._create_hier_pin(
                f"in_{i}", self.drive_port.protocol, "I", port.width
            )
            port_in.connect(port)

            # Check if slice needs to be used
            if bit_high - bit_low + 1 < port.width:
                slice_used = True
                self._new_instance(
                    "xilinx.com:ip:xlslice:1.0",
                    f"slice_{i}",
                    {
                        "CONFIG.DIN_WIDTH": port.width,
                        "CONFIG.DIN_FROM": bit_high,
                        "CONFIG.DIN_TO": bit_low,
                    },
                )
                port_in.connect_internal(f"slice_{i}/din")
            else:
                slice_used = False

            if concat_used and slice_used:
                self._connect_internal_pins_regular(f"slice_{i}/dout", f"concat/In{i}")
            elif concat_used:
                port_in.connect_internal(f"concat/In{i}")
            elif slice_used:
                port_out.connect_internal(f"slice_{i}/dout")
            else:
                port_out.connect(port_in)
