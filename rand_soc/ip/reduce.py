from ..utils import divide_into_groups
from .ip_base import IP


class Reduce(IP):
    def __init__(self, design, name, protocol, in_size, out_size):
        super().__init__(design, name)
        self.protocol = protocol
        self.in_size = in_size
        self.out_size = out_size
        self.instance()

    @property
    def name(self):
        return "reduce"

    def instance(self):
        super().instance()

        self.in_port = self._create_hier_pin("in0", self.protocol, "I", self.in_size)
        self.out_port = self._create_hier_pin("out0", self.protocol, "O", self.out_size)

        in_per_out = divide_into_groups(self.in_size, self.out_size)

        self._new_instance(
            "xilinx.com:ip:xlconcat:2.1",
            "concat",
            {"CONFIG.NUM_PORTS": self.out_size},
        )
        self.out_port.connect_internal("concat/dout")

        bit_low = 0
        for i, reduce_size in enumerate(in_per_out):
            self._new_instance(
                "xilinx.com:ip:xlslice:1.0",
                f"slice_{i}",
                {
                    "CONFIG.DIN_WIDTH": self.in_size,
                    "CONFIG.DIN_FROM": bit_low + reduce_size - 1,
                    "CONFIG.DIN_TO": bit_low,
                },
            )
            bit_low += reduce_size
            self.in_port.connect_internal(f"slice_{i}/din")

            self._new_instance(
                "xilinx.com:ip:util_reduced_logic:2.0",
                f"reduce_{i}",
                {"CONFIG.C_OPERATION": "XOR", "CONFIG.C_SIZE": reduce_size},
            )
            self._connect_internal_pins_regular(f"slice_{i}/dout", f"reduce_{i}/Op1")
            self._connect_internal_pins_regular(f"reduce_{i}/Res", f"concat/In{i}")
