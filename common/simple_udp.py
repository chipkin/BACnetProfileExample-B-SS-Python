# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.

# simple_udp.py
# =============================================================================
# A minimal UDP wrapper for the BACnet examples - the Python edition of the
# C++ examples' common/SimpleUDP.{h,cpp} (and the C# edition's
# common/SimpleUDP.cs), with the same responsibilities:
#
#   - own ONE datagram socket bound to the BACnet/IP port,
#   - let the stack PULL inbound datagrams one at a time (recv()) from its
#     receive callback (the stack never owns the socket - the application
#     does),
#   - send outbound datagrams where the stack's send callback points.
#
# Unlike a queue-based design (e.g. an event-driven Node.js socket), this is
# poll-based: recv() calls the OS socket's recvfrom() directly, non-blocking,
# on every stack tick. That keeps this whole class single-threaded, matching
# the C++/C# editions' synchronous model - there is no lock anywhere in this
# file, and there must not be a background thread touching this socket (the
# CAS BACnet Stack is single-threaded by contract - see AGENTS.md).
#
# The class never sees a BACnet "connection string" - it deals in host-order
# ip/port pairs. Packing the 6-byte connection string (4 IP octets + 2 port
# bytes, port BIG-endian) is cas_example_helper's job, exactly as in the
# C++/C# editions.
# =============================================================================

import socket


class ReceivedDatagram:
    """One received datagram, handed to the stack's receive callback."""

    __slots__ = ("message", "from_ip", "from_port")

    def __init__(self, message, from_ip, from_port):
        self.message = message
        self.from_ip = from_ip
        self.from_port = from_port


class SimpleUDP:
    """An application-owned, non-blocking UDP socket."""

    def __init__(self):
        self._socket = None

    def setup(self, port):
        """Bind the socket. Raises OSError on bind failure (for example:
        another BACnet device already owns the port exclusively)."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind(("0.0.0.0", port))
        # Non-blocking: recv() must return immediately (None if nothing is
        # waiting) so BACnetStack_Tick() is never delayed by a socket read -
        # this class is polled once per tick from main.py's own loop, not
        # from a background thread.
        self._socket.setblocking(False)

    def recv(self):
        """The next queued inbound datagram, or None if none arrived."""
        if self._socket is None:
            return None
        try:
            # 2048 bytes: comfortably larger than the BACnet/IP APDU max (1497).
            message, address = self._socket.recvfrom(2048)
        except (BlockingIOError, InterruptedError):
            return None  # nothing waiting this tick
        except OSError as ex:
            print("Error: UDP receive failed:", ex)
            return None
        from_ip, from_port = address
        return ReceivedDatagram(message, from_ip, from_port)

    def send(self, message, to_ip, to_port):
        """Send one datagram. Fire-and-forget by design: UDP gives no
        delivery guarantee anyway, so a send error is logged, not raised -
        same behaviour as the C++/C# SimpleUDP.Send."""
        if self._socket is None:
            return
        try:
            self._socket.sendto(message, (to_ip, to_port))
        except OSError as ex:
            print(f"Error: UDP send to {to_ip}:{to_port} failed:", ex)

    def shutdown(self):
        """Close the socket."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
