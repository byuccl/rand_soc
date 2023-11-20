import random

import jinja2

from .ports import Port
from .utils import pull_from_list
from .gpio import Gpio
from .microblaze import Microblaze


class DesignCreator:
    def __init__(self):
        random.seed(0)

    def run(self, output_dir_path, num_designs):
        for i in range(num_designs):
            # Create design directory
            output_path = output_dir_path / f"design_{i}"
            output_path.mkdir(parents=True, exist_ok=True)

            design = RandomDesign()
            design.create()
            with open(output_path / "design.tcl", "w", encoding="utf-8") as f:
                f.write(design.tcl_str)


class RandomDesign:
    def __init__(self):
        self.tcl_str = ""
        self._bd_str = ""
        self.ip = []

    def create(self):
        project_config = {"part": "xc7a200tsbg484-1", "bd_name": "design_1"}

        env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

        template = env.get_template("run.tcl.j2")

        ip_idx = 0
        ip_available = [Gpio, Microblaze]
        for ip in ip_available:
            num_ip = random.randint(1, 3)
            for _ in range(num_ip):
                self.ip.append(ip(f"ip_{ip_idx}"))
                ip_idx += 1

        for ip in self.ip:
            ip.randomize()

        for ip in self.ip:
            ip.instance()
            self._bd_str += ip.instance_str

        self._ports()

        project_config["block_diagram"] = self._bd_str
        self.tcl_str = template.render(project_config)

    def _ports(self):
        all_ports = [port for ip in self.ip for port in ip.ports]

        # Reset ports
        reset_ports = []
        pull_from_list(all_ports, reset_ports, lambda p: p.protocol == "reset")
        self._resets(reset_ports)

        # Clock ports
        clock_ports = []
        pull_from_list(all_ports, clock_ports, lambda p: p.protocol == "clk")
        self._clocks(clock_ports)

        # GPIO ports
        gpio_ports = []
        pull_from_list(
            all_ports,
            gpio_ports,
            lambda p: p.protocol == "xilinx.com:interface:gpio_rtl:1.0",
        )
        self._gpio(gpio_ports)

        # AXI ports
        axi_ports = []
        pull_from_list(
            all_ports,
            axi_ports,
            lambda p: p.protocol == "xilinx.com:interface:aximm_rtl:1.0",
        )
        self._axi(axi_ports)

        for port in all_ports:
            print("Unhandled port:", port)
        if all_ports:
            raise Exception("Unhandled ports")

    def _clocks(self, clock_ports):
        # Create single external clock
        self._bd_str += "\n########## Clocks ##########\n"
        self._new_instance("xilinx.com:ip:clk_wiz:6.0", "clk_gen")
        self._create_external_port(
            Port("clk", "I", width=1, protocol="clk"), (Port("clk_gen/clk_in1"),)
        )
        self._connect_port(self.reset_port, Port("clk_gen/reset"))
        self.clock_port = Port("clk_gen/clk_out1", protocol="clk")
        for clock_port in clock_ports:
            self._connect_port(self.clock_port, clock_port)

    def _resets(self, reset_ports):
        # Create single external reset
        self._bd_str += "\n########## Resets ##########\n"
        self.reset_port = Port("reset", "I", width=1, protocol="reset")
        self._create_external_port(self.reset_port, reset_ports)

    def _gpio(self, ports):
        # Create external outputs
        self._bd_str += "\n########## GPIO ##########\n"
        for port in ports:
            self._create_external_port(
                Port(
                    f"{port.ip.hier_name}_{port.name}",
                    protocol=port.protocol,
                    mode=port.mode,
                ),
                (port,),
            )

    def _axi(self, ports):
        """Create AXI ports"""
        masters = [p for p in ports if p.mode == "Master"]
        slaves = [p for p in ports if p.mode == "Slave"]

        # TODO: Non-complete crossbars
        assert len(slaves) > 0

        self._bd_str += "\n########## AXI ##########\n"
        self._new_instance(
            "xilinx.com:ip:smartconnect:1.0",
            "axi",
            {"CONFIG.NUM_MI": len(slaves), "CONFIG.NUM_SI": len(masters)},
        )
        for i, master in enumerate(masters):
            self._connect_port(
                master,
                Port(
                    f"axi/S{i:02}_AXI",
                    protocol="xilinx.com:ip:smartconnect:1.0",
                ),
            )
        for i, slave in enumerate(slaves):
            self._connect_port(
                slave,
                Port(
                    f"axi/M{i:02}_AXI",
                    protocol="xilinx.com:ip:smartconnect:1.0",
                ),
            )
            for master in masters:
                self._assign_bd_address(master, slave)
        self._connect_port(self.clock_port, Port("axi/aclk"))
        self._connect_port(self.reset_port, Port("axi/aresetn"))

        # assign_bd_address -target_address_space /ip_0_microblaze/microblaze_0/Data [get_bd_addr_segs ip_2_gpio/gpio_0/S_AXI/Reg] -force

    def _create_external_port(self, port, connect_to_ports=None):
        assert isinstance(port, Port)
        if port.protocol.startswith("xilinx.com:interface:"):
            self._bd_str += f"create_bd_intf_port -mode {port.mode} -vlnv {port.protocol} {port.name}\n"
        else:
            self._bd_str += f"create_bd_port -dir {port.direction} -from {port.width-1} -to 0 {port.name}\n"
        if connect_to_ports:
            for port_to in connect_to_ports:
                self._connect_port(port, port_to)

    def _connect_port(self, port1, port2):
        assert isinstance(port1, Port)
        assert isinstance(port2, Port)
        if port1.protocol.startswith("xilinx.com:interface:"):
            self._bd_str += f"connect_bd_intf_net [get_bd_intf_pins {port1.hier_name}] [get_bd_intf_pins {port2.hier_name}]\n"
        else:
            self._bd_str += f"connect_bd_net [get_bd_pins {port1.hier_name}] [get_bd_pins {port2.hier_name}]\n"

    def _new_instance(self, ip_name, instance_name, properties=None):
        self._bd_str += f"create_bd_cell -type ip -vlnv {ip_name} {instance_name}\n"
        if properties:
            self._set_instance_properties(instance_name, properties)

    def _set_instance_properties(self, instance_name, properties):
        # Combine key, value pairs into a single string
        prop = ""
        for key, value in properties.items():
            prop += f"{key} {value} "
        self._bd_str += f'set_property -dict "{prop}" [get_bd_cells {instance_name}]\n'

    def _assign_bd_address(self, master_port, slave_port):
        # assign_bd_address -target_address_space /ip_0_microblaze/microblaze_0/Data [get_bd_addr_segs ip_2_gpio/gpio_0/S_AXI/Reg] -force
        self._bd_str += f"assign_bd_address -target_address_space /{master_port.ip.hier_name}/{master_port.addr_seg_name} [get_bd_addr_segs {slave_port.ip.hier_name}/{slave_port.addr_seg_name}] -force\n"
