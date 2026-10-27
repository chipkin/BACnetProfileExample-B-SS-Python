# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.

# cas_example_helper.py
# =============================================================================
# Shared plumbing for the BACnet examples - the Python edition of the C++
# examples' common/CASExampleHelper.{h,cpp} (and the C# edition's
# common/CASExampleHelper.cs), same responsibilities, same names:
#
#   - setup_udp() / register_common_callbacks(): bind the BACnet/IP socket and
#     register the three transport/time callbacks every example needs
#     (receive, send, system time). This is where the 6-byte IPv4 connection
#     string lives: 4 IP octets then the port in BIG-endian byte order -
#     written here ONCE so no example re-derives it. Every datagram received
#     or sent is printed as one console line ("RX 25 bytes from ...",
#     "TX 25 bytes to ... (broadcast)"), the C++ edition's format.
#   - send_i_am(): the unsolicited I-Am every example transmits on start-up.
#   - get_local_ipv4(): the primary interface's address/netmask/broadcast (the
#     OS-level plumbing the Network Port object reports).
#   - the command line (handle_help_and_version_args(), parse_port_arg(),
#     parse_device_id_arg(), parse_device_name_arg()), the version banner
#     (print_version()) and the interactive keys (poll_key(), print_help(),
#     restore_input()).
#
# THE ADAPTER IS USED IN PLACE. This module imports the CAS BACnet Stack's own
# generated Python adapter, CASBACnetStackAdapterBindings.py, straight from
# submodules/cas-bacnet-stack/adapters/python/ (or from the run directory) -
# main.py puts those folders on sys.path before importing this module. Nothing of the adapter is copied into
# this repository: it is part of the commercially licensed stack, and the
# stack's generator (_ci_scripts/generate-python-adapter.js) owns it.
#
# The stack PULLS datagrams: its receive callback asks for one queued
# datagram per call and the stack never touches the socket. The application
# (SimpleUDP) owns the socket - keep that split in your own project.
#
# PORT-KEYED TRANSPORT. A link is identified by the Network Port object's
# INSTANCE, not by a transport-type enumeration:
# BACnetStack_RegisterCallbackReceiveMessageForPort /
# BACnetStack_RegisterCallbackSendMessageForPort take/report a
# networkPortInstance, and BACnetStack_SendIAm's fourth argument is that same
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

import ctypes
import os
import socket
import sys
import time

try:
    # The adapter, in place (main.py puts its folders on sys.path). Imported
    # optionally so --help, --version and the missing-library message still
    # work in a release, which does not include the stack.
    import CASBACnetStackAdapterBindings as bacnet
except ImportError:
    bacnet = None

# The version of the vendored common/ helper itself (NOT the example's
# version). Bump it whenever anything in common/ changes, and record the
# change in common/CHANGELOG.md.
COMMON_VERSION = "1.2.0"

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
    see common/README.md "Why no netmask discovery"). Instead this function
    opens a UDP socket "connected" to a public address (no packet is actually
    sent - UDP connect() only asks the OS to pick a local source
    address/route) to learn the outbound-interface IP, and ASSUMES a /24
    (255.255.255.0) netmask, which is correct on most flat home/office/lab
    networks but not on every network. If your subnet is not a /24, pass a
    real IP_Address / IP_Subnet_Mask into the Network Port some other way
    (e.g. read it from the OS's own tools, or add a --netmask flag) rather
    than trusting this function blindly in production.
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
# The socket and the three common callbacks
# -----------------------------------------------------------------------------

def setup_udp(udp, port, network_port_instance):
    """Bind `udp` (a SimpleUDP) to `port`. Prints why and returns False if the
    port cannot be bound - for example, another BACnet device already owns
    it."""
    try:
        udp.setup(port)
    except OSError as ex:
        print(f"Error: Failed to bind UDP port {port} (Network Port {network_port_instance}): {ex}")
        return False
    print(f"FYI: Listening for BACnet/IP on UDP port {port} (Network Port {network_port_instance}).")
    return True


def register_common_callbacks(udp, network_port_instance):
    """Register the receive/send/system-time callbacks against one bound
    SimpleUDP, for the given Network Port object instance. Call once, after
    bacnet.bind(library) and setup_udp(), and before BACnetStack_AddDevice.

    Args:
        udp: the SimpleUDP this example owns, already bound (setup_udp()).
        network_port_instance: the instance passed to
            BACnetStack_AddNetworkPortObject for this socket (this example:
            NETWORK_PORT_INSTANCE, 1).
    """
    # Read once, not on every send: the address the send callback compares
    # against, and the local subnet broadcast it substitutes.
    local = get_local_ipv4()

    def on_receive(message, max_message_length, source_connection_string,
                   source_connection_string_length, destination_connection_string,
                   destination_connection_string_length, max_connection_string_length,
                   out_network_port_instance):
        if max_connection_string_length < 6:
            return 0  # cannot even fit an IPv4 connection string
        datagram = udp.recv()
        if datagram is None:
            return 0  # nothing waiting this tick
        # A datagram larger than the stack's buffer is truncated to that length
        # (the C++ edition does the same): the stack fails to decode it and
        # ignores it.
        length = min(len(datagram.message), max_message_length)
        ctypes.memmove(message, datagram.message, length)
        print(f"RX {length} bytes from {datagram.from_ip}:{datagram.from_port} "
              f"(Network Port {network_port_instance})")
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

    # A NULL / length-0 connection string is the stack saying "broadcast on
    # this data link" (BACnetStack_RegisterCallbackSendMessageForPort's
    # contract in CASBACnetStackDLL.h): it goes to the local subnet broadcast
    # on this socket's port (C++ common/ 3.2.0). broadcast = True WITH an
    # address normally means "send to this address"; the one exception is
    # THIS socket's own address and port, which the stack passes when it
    # means "this subnet" (a Device_Address_Binding Who-Is copies the address
    # of the last I-Am heard - this device's own, looped back; stack issue
    # #3933), so that also goes to the local subnet broadcast (C++ common/
    # 3.4.0). Every other address is sent to as given. A connection string of
    # 1-5 octets is not a BACnet/IP address and is refused.
    def on_send(message, message_length, connection_string, connection_string_length,
                send_network_port_instance, broadcast):
        if send_network_port_instance != network_port_instance:
            return 0  # this example owns exactly one Network Port
        is_broadcast = bool(broadcast)
        if not connection_string or connection_string_length == 0:
            to_ip, to_port = local.broadcast, udp.port
            is_broadcast = True
        elif connection_string_length < 6:
            return 0
        else:
            to_ip = ".".join(str(connection_string[i]) for i in range(4))
            to_port = (connection_string[4] << 8) | connection_string[5]
            if broadcast and to_port == udp.port and to_ip == local.address:
                to_ip = local.broadcast
        sent = udp.send(ctypes.string_at(message, message_length), to_ip, to_port)
        print(f"TX {sent} bytes to {to_ip}:{to_port}{' (broadcast)' if is_broadcast else ''} "
              f"(Network Port {send_network_port_instance})")
        return sent

    # CASBACnetTime: int64 seconds since the UNIX epoch.
    def on_get_system_time():
        return int(time.time())

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
            example: NETWORK_PORT_INSTANCE, 1) - BACnetStack_SendIAm's fourth
            argument identifies the LINK by Network Port instance, not by a
            transport-type enumeration.

    Returns:
        BACnetStack_SendIAm's own result.
    """
    local = get_local_ipv4()
    octets = [int(part) for part in local.broadcast.split(".")]
    connection_string = (ctypes.c_uint8 * 6)(
        octets[0], octets[1], octets[2], octets[3],
        (udp_port >> 8) & 0xFF, udp_port & 0xFF,
    )
    return bacnet.BACnetStack_SendIAm(
        device_instance, connection_string, 6, network_port_instance,
        True,  # broadcast
        0,     # destinationNetwork: the local network only (not the global 0xFFFF)
        None, 0,
    )


# -----------------------------------------------------------------------------
# Version banner and command line
# -----------------------------------------------------------------------------

def print_version(app_name, app_version):
    print(f"{app_name} v{app_version}")
    if bacnet is not None and bacnet.is_bound():
        print("CAS BACnet Stack version: {}.{}.{}.{}".format(
            bacnet.BACnetStack_GetAPIMajorVersion(),
            bacnet.BACnetStack_GetAPIMinorVersion(),
            bacnet.BACnetStack_GetAPIPatchVersion(),
            bacnet.BACnetStack_GetAPIBuildVersion(),
        ))
    else:
        print("CAS BACnet Stack version: not loaded (the library was not found)")
    # The vendored common/ helper has its own version (see common/CHANGELOG.md)
    # so it is easy to tell whether this example's copy is stale.
    print(f"Common helper (common/) version: {COMMON_VERSION}")


def print_missing_stack_library(missing_file, searched_directories):
    """The series' message (the same in every language port) for a run without
    the CAS BACnet Stack, to stderr. The caller then exits with code 1."""
    looked_in = ("\n" + " " * 16).join(searched_directories)
    print(f"""ERROR: This example cannot run without the CAS BACnet Stack library.

  Missing file: {missing_file}
  Looked in:    {looked_in}

The CAS BACnet Stack is a commercially licensed (paid) library from Chipkin.
It is not included in this release, so the example cannot start without it.

  - To license the CAS BACnet Stack: https://store.chipkin.com/contact-us
  - Licensed customers: build the library from the cas-bacnet-stack submodule
    (see README.md) and place {missing_file} next to this executable.""", file=sys.stderr)


def print_interactive_commands():
    """Just the interactive key list, with no version banner - so the two
    callers that already printed one (print_help for the 'h' key, and the
    --help handler) do not print it twice."""
    print("Commands:")
    print("  h     - show this help (version + commands)")
    print("  q     - quit")
    print("  up    - increase Analog Input 1 by 1.1")
    print("  down  - decrease Analog Input 1 by 1.1")


def print_help(app_name, app_version):
    print_version(app_name, app_version)
    print_interactive_commands()


def handle_help_and_version_args(argv, app_name, app_version, show_device_name_cli_option=False):
    """--help / -h / /? print the version banner, the options and the keys;
    --version prints the version banner. Returns True if one was handled (the
    caller exits), False otherwise. show_device_name_cli_option lists
    --deviceName, for an example that reads it (parse_device_name_arg(); added
    in 1.2.0 - the default, False, prints exactly what 1.1.0 printed)."""
    for argument in argv[1:]:
        if argument in ("--help", "-h", "/?"):
            print_version(app_name, app_version)
            print()
            print("Usage: python main.py [options]")
            print()
            print("Options:")
            print("  --help, -h        Show this help and exit.")
            print("  --version         Show version information and exit.")
            print("  --deviceID <n>    BACnet device instance (0..4194302). Each example in")
            print("                    this series has its own default so several can run on")
            print("                    one subnet at once.")
            if show_device_name_cli_option:
                print("  --deviceName <text>")
                print(f"                    The Device object's Object_Name (1..{MAX_DEVICE_NAME_LENGTH} bytes, no")
                print("                    control characters). It must be unique across the BACnet")
                print("                    internetwork, so give every unit its own. Default: this")
                print("                    example's own name.")
            print("  --port <n>        BACnet/IP UDP port (1..65535). Default 47808 (0xBAC0).")
            print("                    Use a non-default port to avoid clashing with another")
            print("                    BACnet device already on 47808 on this host.")
            print()
            print_interactive_commands()  # version banner already printed above
            return True
        if argument == "--version":
            print_version(app_name, app_version)
            return True
    return False


def _parse_whole_number(text):
    """The value of `text` if the WHOLE token is a non-negative decimal
    integer, else None. int() alone would accept " 12", "+12" and "1_2"; the
    C++ edition's strtol + end-pointer check accepts none of them, and a typo
    must be rejected rather than silently obeyed as a different number."""
    if not text or not text.isdigit() or not text.isascii():
        return None
    return int(text)


def parse_port_arg(argv, default_port):
    """--port <n>: 1..65535. An invalid value prints a warning and the default
    is used (the C++ edition's ParsePortArg)."""
    for i in range(1, len(argv) - 1):
        if argv[i] == "--port":
            port = _parse_whole_number(argv[i + 1])
            if port is not None and 0 < port <= 65535:
                return port
            print(f'Warning: ignoring invalid --port "{argv[i + 1]}" (want 1..65535); using {default_port}.')
    return default_port


def parse_device_id_arg(argv, default_device_id):
    """--deviceID <n>: 0..4194302 (4194303 is the "unconfigured" wildcard and
    is not a usable instance). An invalid value prints a warning and the
    default is used (the C++ edition's ParseDeviceIdArg)."""
    for i in range(1, len(argv) - 1):
        if argv[i] == "--deviceID":
            device_id = _parse_whole_number(argv[i + 1])
            if device_id is not None and device_id < 4194303:
                return device_id
            print(f'Warning: ignoring invalid --deviceID "{argv[i + 1]}" (want 0..4194302); '
                  f"using {default_device_id}.")
    return default_device_id


# The longest Device Object_Name --deviceName accepts, in UTF-8 bytes.
MAX_DEVICE_NAME_LENGTH = 255


def parse_device_name_arg(argv, default_device_name):
    """--deviceName <text>: the Device object's Object_Name. Object_Name must be
    unique across the BACnet internetwork (cl. 12.1.1.4, 12.11), so two units
    that share a compile-time name are non-conformant the moment both are
    installed; this makes it per-unit configurable at start-up, the way
    --deviceID makes the instance configurable. Valid = 1..MAX_DEVICE_NAME_LENGTH
    bytes of UTF-8 and no control characters (a name must be printable);
    anything else prints a warning and the default is used. The same rules as
    the C++ edition's ParseDeviceNameArg()."""
    for i in range(1, len(argv) - 1):
        if argv[i] != "--deviceName":
            continue
        name = argv[i + 1]
        try:
            length = len(name.encode("utf-8"))
        except UnicodeEncodeError:  # an undecodable command-line byte (a lone surrogate)
            length = 0
        printable = 0 < length <= MAX_DEVICE_NAME_LENGTH and not any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in name)
        if printable:
            return name
        print(f"Warning: ignoring invalid --deviceName (want 1..{MAX_DEVICE_NAME_LENGTH} bytes, "
              f'no control characters); using "{default_device_name}".')
    return default_device_name


# -----------------------------------------------------------------------------
# Interactive keys
#
# poll_key() returns the key pressed since the last call, or KeyCommand.NONE -
# it never blocks, so the main loop's BACnetStack_Tick() keeps running:
#
#   - Windows console: msvcrt.kbhit() / getch() (the C++ edition's
#     _kbhit() / _getch()).
#   - POSIX: stdin is made non-blocking and, when it is a terminal, put into
#     cbreak mode (no line buffering, no echo); each call read()s what is
#     waiting (the C++ edition's EnableRawInput() + read()). A pipe works the
#     same way, which is how a test harness writes 'q' to stop the example.
#   - Windows, stdin redirected (a pipe): a pipe has no non-blocking "is a key
#     waiting" check there, so a daemon thread reads it and queues 'q' / 'h'
#     for poll_key(). The thread touches nothing but that queue - never the
#     stack, never the socket. (The C++ edition does not read a redirected
#     stdin on Windows at all; this lets the Wire Tests' harness stop the
#     example with 'q' on every platform.)
# -----------------------------------------------------------------------------

class KeyCommand:
    NONE = "none"
    HELP = "help"         # 'h' - show version + commands
    QUIT = "quit"         # 'q' - exit
    ARROW_UP = "up"       # up arrow
    ARROW_DOWN = "down"   # down arrow


_LETTER_KEYS = {"h": KeyCommand.HELP, "q": KeyCommand.QUIT}
_input_configured = False
_restore_actions = []
_piped_keys = None


def _configure_input():
    global _input_configured, _piped_keys
    _input_configured = True
    if sys.stdin is None:
        return
    if os.name == "nt":
        if not sys.stdin.isatty():
            import queue
            import threading
            _piped_keys = queue.SimpleQueue()
            descriptor = sys.stdin.fileno()

            # os.read() on the raw descriptor, not sys.stdin.buffer: the
            # buffered reader holds a lock while it waits, and a daemon thread
            # still holding it when the interpreter exits is a fatal error.
            def read_piped_keys():
                try:
                    while True:
                        character = os.read(descriptor, 1)
                        if not character:
                            return  # end of input
                        key = _LETTER_KEYS.get(character.decode("ascii", "replace").lower())
                        if key is not None:
                            _piped_keys.put(key)
                except (OSError, ValueError):
                    return

            threading.Thread(target=read_piped_keys, daemon=True).start()
        return

    # POSIX. Non-blocking FIRST and unconditionally (a pipe with no data yet
    # must never block the tick loop), then cbreak mode only for a terminal.
    import fcntl
    import termios
    import tty
    descriptor = sys.stdin.fileno()
    flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    fcntl.fcntl(descriptor, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    _restore_actions.append(lambda: fcntl.fcntl(descriptor, fcntl.F_SETFL, flags))
    if os.isatty(descriptor):
        original = termios.tcgetattr(descriptor)
        tty.setcbreak(descriptor)
        _restore_actions.append(lambda: termios.tcsetattr(descriptor, termios.TCSADRAIN, original))


def poll_key():
    """The key pressed since the last call, or KeyCommand.NONE. Never blocks."""
    if not _input_configured:
        _configure_input()
    if sys.stdin is None:
        return KeyCommand.NONE
    if os.name == "nt":
        if _piped_keys is not None:
            return KeyCommand.NONE if _piped_keys.empty() else _piped_keys.get()
        import msvcrt
        if not msvcrt.kbhit():
            return KeyCommand.NONE
        character = msvcrt.getch()
        if character in (b"\x00", b"\xe0"):  # arrow / function key prefix
            second = msvcrt.getch()
            if second == b"H":
                return KeyCommand.ARROW_UP
            if second == b"P":
                return KeyCommand.ARROW_DOWN
            return KeyCommand.NONE
        return _LETTER_KEYS.get(character.decode("ascii", "replace").lower(), KeyCommand.NONE)

    try:
        typed = os.read(sys.stdin.fileno(), 3)
    except (BlockingIOError, InterruptedError):
        return KeyCommand.NONE
    except OSError:
        return KeyCommand.NONE
    if not typed:
        return KeyCommand.NONE  # end of input
    if len(typed) >= 3 and typed[0] == 27 and typed[1] == ord("["):  # ESC [ A/B = arrow keys
        return {ord("A"): KeyCommand.ARROW_UP, ord("B"): KeyCommand.ARROW_DOWN}.get(typed[2], KeyCommand.NONE)
    return _LETTER_KEYS.get(chr(typed[0]).lower(), KeyCommand.NONE)


def restore_input():
    """Put the terminal back the way it was (POSIX); nothing to do on Windows.
    Call once before the program exits."""
    while _restore_actions:
        try:
            _restore_actions.pop()()
        except (OSError, ValueError):
            pass
