# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.

# cas_example_helper.py
# =============================================================================
# Shared plumbing for the BACnet examples - the Python edition of the C++
# examples' common/CASExampleHelper.{h,cpp} (and the C# edition's
# common/CASExampleHelper.cs), same responsibilities, same names:
#
#   - register_common_callbacks(): the three transport/time callbacks every
#     example needs (receive, send, system time). This is where the 6-byte
#     IPv4 connection string lives: 4 IP octets then the port in BIG-endian
#     byte order - written here ONCE so no example re-derives it.
#   - send_i_am(): the unsolicited I-Am every example transmits on start-up.
#   - get_local_ipv4(): the primary interface's address/netmask/broadcast (the
#     OS-level plumbing the Network Port object reports).
#   - CLI helpers (--deviceID/--port validation) + print_version().
#
# The stack PULLS datagrams: its receive callback asks for one queued
# datagram per call and the stack never touches the socket. The application
# (SimpleUDP) owns the socket - keep that split in your own project.
#
# PORT-KEYED TRANSPORT (this example's stack pin, branch `6.x`). A link is
# identified by the Network Port object's INSTANCE, not by a transport-type
# enumeration: BACnetStack_RegisterCallbackReceiveMessageForPort /
# BACnetStack_RegisterCallbackSendMessageForPort take/report a
# networkPortInstance, and BACnetStack_SendIAm's fifth argument is that same
# instance. This example has exactly one Network Port (instance 1,
# "Vermilion" - see NETWORK_PORT_INSTANCE in main.py), so every call below
# names it directly rather than looping over a port table.
#
# CALLBACKS MUST BE ROOTED. ctypes.CFUNCTYPE(...) wraps a Python callable in
# a native-callable thunk, but ctypes keeps NO reference of its own to that
# wrapper object. If it is garbage-collected while the native stack may still
# call it, the NEXT call into it is a crash (a bad function pointer, not a
# clean Python exception). Every CFUNCTYPE object this module creates is
# appended to the module-level _callback_refs list below and never assigned
# only to a local variable - that list is what keeps them alive for the life
# of the process. See AGENTS.md for the same rule applied to main.py's
# Get*Property callbacks.
# =============================================================================

import socket
from argparse import ArgumentTypeError

import cas_bacnet_stack.CASBACnetStackAdapterBindings as bacnet

# The version of the vendored common/ helper itself (NOT the example's
# version). Bump it whenever anything in common/ changes, and record the
# change in common/CHANGELOG.md.
COMMON_VERSION = "1.0.0"

# Every ctypes.CFUNCTYPE callback object registered with the stack is kept
# here for the life of the process - see the module docstring above. Do NOT
# store one only in a local variable inside a function; append it here first.
_callback_refs = []


# -----------------------------------------------------------------------------
# Local IPv4 discovery
# -----------------------------------------------------------------------------

class LocalIPv4:
    """The primary non-loopback IPv4 interface's address/netmask/broadcast."""

    __slots__ = ("address", "netmask", "broadcast")

    def __init__(self, address, netmask, broadcast):
        self.address = address
        self.netmask = netmask
        self.broadcast = broadcast


def get_local_ipv4():
    """The primary IPv4 interface's address, guessed netmask, and derived
    broadcast address. The Network Port object reports these values, and
    send_i_am() targets the derived subnet broadcast.

    DEVIATION FROM THE C++/C# EDITIONS: those use OS-specific interface
    enumeration (getifaddrs / NetworkInterface.GetAllNetworkInterfaces) to
    read the REAL subnet mask. The Python standard library has no portable
    equivalent (a real one needs a third-party package such as `netifaces` or
    `psutil`, which this example deliberately avoids to stay stdlib-only -
    see README.md "Why no netmask discovery"). Instead this function opens a
    UDP socket "connected" to a public address (no packet is actually sent -
    UDP connect() only asks the OS to pick a local source address/route) to
    learn the outbound-interface IP, and ASSUMES a /24 (255.255.255.0)
    netmask, which is correct on most flat home/office/lab networks but not
    on every network. If your subnet is not a /24, pass a real IP_Address /
    IP_Subnet_Mask into the Network Port some other way (e.g. read it from
    the OS's own tools, or add a --netmask flag) rather than trusting this
    function blindly in production.
    """
    address = "127.0.0.1"
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        pass  # no network: loopback keeps the example runnable offline

    if address == "127.0.0.1":
        return LocalIPv4("127.0.0.1", "255.0.0.0", "127.255.255.255")

    netmask = "255.255.255.0"
    ip_octets = [int(part) for part in address.split(".")]
    mask_octets = [int(part) for part in netmask.split(".")]
    broadcast_octets = [ip_octets[i] | (~mask_octets[i] & 0xFF) for i in range(4)]
    broadcast = ".".join(str(o) for o in broadcast_octets)
    return LocalIPv4(address, netmask, broadcast)


# -----------------------------------------------------------------------------
# The three common callbacks
# -----------------------------------------------------------------------------

def register_common_callbacks(udp, network_port_instance):
    """Register the receive/send/system-time callbacks against one
    SimpleUDP, for the given Network Port object instance. Call once, after
    bacnet.bind(library) and before BACnetStack_AddDevice.

    Args:
        udp: the SimpleUDP this example owns.
        network_port_instance: the instance passed to
            BACnetStack_AddNetworkPortObject for this socket (this example:
            NETWORK_PORT_INSTANCE, 1).
    """

    def on_receive(message, max_message_length, source_connection_string,
                    source_connection_string_length, destination_connection_string,
                    destination_connection_string_length, max_connection_string_length,
                    out_network_port_instance):
        # The out-params arrive UNINITIALIZED - write every one we do not
        # fill with real data, or the stack reads garbage.
        source_connection_string_length[0] = 0
        destination_connection_string_length[0] = 0
        if max_connection_string_length < 6:
            return 0  # cannot even fit an IPv4 connection string
        datagram = udp.recv()
        if datagram is None:
            return 0  # nothing waiting this tick
        length = len(datagram.message)
        if length > max_message_length:
            print(f"Error: dropping {length}-byte datagram from "
                  f"{datagram.from_ip}:{datagram.from_port} - larger than the "
                  f"stack's {max_message_length}-byte receive buffer.")
            return 0
        for i in range(length):
            message[i] = datagram.message[i]
        # 6-byte IPv4 connection string: 4 IP octets, then the port BIG-endian.
        octets = [int(part) for part in datagram.from_ip.split(".")]
        for i in range(4):
            source_connection_string[i] = octets[i]
        source_connection_string[4] = (datagram.from_port >> 8) & 0xFF
        source_connection_string[5] = datagram.from_port & 0xFF
        source_connection_string_length[0] = 6
        # Which Network Port object this datagram arrived on.
        out_network_port_instance[0] = network_port_instance
        return length

    def on_send(message, message_length, connection_string, connection_string_length,
                send_network_port_instance, broadcast):
        if connection_string_length < 6:
            return 0
        to_ip = ".".join(str(connection_string[i]) for i in range(4))
        to_port = (connection_string[4] << 8) | connection_string[5]
        buffer = bytes(message[i] for i in range(message_length))
        udp.send(buffer, to_ip, to_port)
        return message_length

    def on_get_system_time():
        import time
        return int(time.time())  # unix epoch SECONDS

    receive_cb = bacnet.FPCallbackReceiveMessageForPort(on_receive)
    send_cb = bacnet.FPCallbackSendMessageForPort(on_send)
    system_time_cb = bacnet.FPCallbackGetSystemTime(on_get_system_time)
    # Root every callback for the life of the process - see the module
    # docstring's "CALLBACKS MUST BE ROOTED" note.
    _callback_refs.append(receive_cb)
    _callback_refs.append(send_cb)
    _callback_refs.append(system_time_cb)

    bacnet.BACnetStack_RegisterCallbackReceiveMessageForPort(receive_cb)
    bacnet.BACnetStack_RegisterCallbackSendMessageForPort(send_cb)
    bacnet.BACnetStack_RegisterCallbackGetSystemTime(system_time_cb)


# -----------------------------------------------------------------------------
# I-Am
# -----------------------------------------------------------------------------

def send_i_am(device_instance, udp_port, network_port_instance):
    """Broadcast an unsolicited I-Am announcing this device - every example
    sends one on start-up. Targets the LOCAL subnet broadcast (the device's
    own network) rather than the global 255.255.255.255 / network 0xFFFF: the
    broadcast is ip | ~mask of the primary IPv4 interface - the same network
    the Network Port object reports.

    Args:
        network_port_instance: the Network Port object to send on (this
            example: NETWORK_PORT_INSTANCE, 1) - BACnetStack_SendIAm's fifth
            argument identifies the LINK by Network Port instance, not by a
            transport-type enumeration.
    """
    import ctypes

    local = get_local_ipv4()
    octets = [int(part) for part in local.broadcast.split(".")]
    connection_string = (ctypes.c_uint8 * 6)(
        octets[0], octets[1], octets[2], octets[3],
        (udp_port >> 8) & 0xFF, udp_port & 0xFF,
    )
    return bacnet.BACnetStack_SendIAm(
        device_instance, connection_string, 6, network_port_instance,
        True,  # broadcast
        0,     # destinationNetwork: local network
        None, 0,
    )


# -----------------------------------------------------------------------------
# CLI helpers
# -----------------------------------------------------------------------------

def print_version(app_name, app_version):
    print(f"{app_name} v{app_version}")
    print("CAS BACnet Stack v{}.{}.{}.{}".format(
        bacnet.BACnetStack_GetAPIMajorVersion(),
        bacnet.BACnetStack_GetAPIMinorVersion(),
        bacnet.BACnetStack_GetAPIPatchVersion(),
        bacnet.BACnetStack_GetAPIBuildVersion(),
    ))


def parse_port(raw):
    """argparse `type=` callback for --port: an integer 1..65535."""
    try:
        value = int(raw)
    except ValueError:
        raise ArgumentTypeError(f'--port expects an integer 1..65535, got "{raw}"')
    if value < 1 or value > 65535:
        raise ArgumentTypeError(f'--port expects an integer 1..65535, got "{raw}"')
    return value


def parse_device_id(raw):
    """argparse `type=` callback for --deviceID: an integer 0..4194302.
    4194303 is the BACnet "unconfigured" sentinel - a real device may not use
    it."""
    try:
        value = int(raw)
    except ValueError:
        raise ArgumentTypeError(f'--deviceID expects an integer 0..4194302, got "{raw}"')
    if value < 0 or value > 4194302:
        raise ArgumentTypeError(f'--deviceID expects an integer 0..4194302, got "{raw}"')
    return value
