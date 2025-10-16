from collections import defaultdict
import logging
import random

from .utils import min_subset_sum_by_key


def port_assigner_random(in_ports, out_ports):
    """Randomly make connection assignments from out_ports to in_ports, such that each in_port is fully driven.
    This does not actually make the connections, it just returns the assignments.

    Returns: a dictionary mapping each in_port to a list of (out_port, high_bit, low_bit) tuples.

    """

    drivers_for_port = defaultdict(list)

    if not in_ports and not out_ports:
        return drivers_for_port

    logging.info(
        f"Will randomly connect {len(out_ports)} output ports to {len(in_ports)} input ports"
    )

    # Generate list of in and out ports, where each item is a tuple (port, index)
    # where index is the lowest bit number not connected
    in_ports_not_driven = [[port, 0] for port in in_ports]
    random.shuffle(in_ports_not_driven)

    out_ports_unused = [[port, 0] for port in out_ports]
    assert out_ports_unused

    # Connect all in ports
    next_out_port_idx = 0

    for in_port_and_pin_idx in in_ports_not_driven:
        drivers = []
        in_port = in_port_and_pin_idx[0]
        in_width = in_port.width
        in_width_unconnected = in_width
        logging.info(f"Connecting drivers of port {in_port.hier_name} [{in_width-1}:0]")

        num_connected = 0

        while in_width_unconnected:
            # Once we've used up all the output signals, this flag will switch to True
            # and we will randomly reuse output signals
            using_random_output = next_out_port_idx >= len(out_ports_unused)

            # Pick the output port
            if using_random_output:
                out_port = random.choice(out_ports_unused)[0]
                out_port_avail = None
                # Randomly pick a pin range to use
                out_width = min(out_port.width, in_width_unconnected)
                out_bit_low = random.randint(0, out_port.width - out_width)
                out_bit_high = out_bit_low + out_width - 1
            else:
                out_port = out_ports_unused[next_out_port_idx][0]
                # Identify unused pins from this port
                out_port_avail = out_ports_unused[next_out_port_idx]
                out_bit_high = out_port_avail[0].width - 1
                out_bit_low = out_port_avail[1]

            out_width = out_bit_high - out_bit_low + 1

            if out_width == in_width_unconnected:
                logging.info(
                    f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
                )
                drivers.append((out_port, out_bit_high, out_bit_low))
                num_connected += out_width
                next_out_port_idx += 1
                in_width_unconnected = 0
                break

            if out_width > in_width_unconnected:
                logging.info(
                    f"  [{in_width_unconnected-1}:0] <-- {out_port.hier_name} [{out_bit_low + in_width_unconnected - 1}:{out_bit_low}]"
                )
                drivers.append(
                    (out_port, out_bit_low + in_width_unconnected - 1, out_bit_low)
                )
                num_connected += in_width_unconnected
                if out_port_avail:
                    out_port_avail[1] += in_width_unconnected
                in_width_unconnected = 0
                break

            # out_width < in_width_unconnected
            logging.info(
                f"  [{in_width_unconnected-1}:{in_width_unconnected-out_width}] <-- {out_port.hier_name} [{out_bit_high}:{out_bit_low}]"
            )
            drivers.append((out_port, out_bit_high, out_bit_low))
            num_connected += out_width
            next_out_port_idx += 1
            in_width_unconnected -= out_width

        assert (
            num_connected == in_width
        ), f"num_connected: {num_connected}, in_width: {in_width}"

        drivers_for_port[in_port] = drivers

    return drivers_for_port


def port_assigner_axis(in_ports, out_ports):
    """Make connection assignments from out_ports to in_ports, such that each in_port is fully driven.
    This does not actually make the connections, it just returns the assignments.

    Returns: a dictionary mapping each in_port to a list of ports from out_ports.

    """

    drivers_for_port = defaultdict(list)

    unassigned_in_ports = list(in_ports)
    unassigned_out_ports = list(out_ports)

    print("here1")

    # Loop through all in_ports, and look for an out_port with the same width,
    # or a combination of out_ports that can be concatenated to match the width.
    #
    # First pass:
    # - don't allow reuse of output ports.
    # - ignore in_ports where no exact match width match is possible
    for in_port in unassigned_in_ports:
        matched_ports = min_subset_sum_by_key(
            unassigned_out_ports, in_port.width, key=lambda x: x.width
        )
        if matched_ports is None:
            continue
        drivers_for_port[in_port] = matched_ports
        unassigned_in_ports.remove(in_port)
        for p in matched_ports:
            unassigned_out_ports.remove(p)

    # Second pass:
    # - Continue this until all out_ports are driving something
    # -
