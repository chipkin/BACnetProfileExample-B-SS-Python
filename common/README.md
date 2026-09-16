# `common/` - shared example plumbing (Python edition)

The helpers every Python example in the BACnet profile example series will
share. **Vendored**: this directory is a *copy* in each example repo, not a
package published to PyPI - change it in one repo and you must sweep the
same change to every sibling and bump `COMMON_VERSION` (in
`cas_example_helper.py`) + add a `CHANGELOG.md` entry. This is the *first*
Python example in the series, so there is no sibling to sweep to yet - the
next Python example in the series starts by copying this folder.

## Versioning

`COMMON_VERSION` in `cas_example_helper.py`, changelog in
`common/CHANGELOG.md`. The Python common versions independently of the
C++/C#/Node `common/` (each at its own version) - same rules, separate
lineage. This copy starts at **1.0.0**: the first Python `common/`, built
against the `submodules/cas-bacnet-stack` `6.x` branch's current
adapter/callback API. See `common/CHANGELOG.md` for what's in it and how the
Python binding mechanism differs from the C++/C# editions.

## What's here

| File | What it is |
|---|---|
| `simple_udp.py` | The UDP socket the application owns: bind, poll for inbound datagrams (non-blocking `recvfrom()`, no background thread), send. The stack never touches the socket - it pulls datagrams through the receive callback. |
| `cas_example_helper.py` | `register_common_callbacks()` (receive/send/system-time + the 6-byte IPv4 connection string, port big-endian, written here ONCE), `send_i_am()`, `get_local_ipv4()`, and CLI validators for use with `argparse`. |
| `cas_bacnet_stack_example_constants.py` | The handful of BACnet enumeration values this example needs, spelled out as named constants so this file diffs 1:1 against the C++/C# editions' equivalents. |

## How main.py uses it

```python
import ctypes
from cas_bacnet_stack.CASBACnetStackAdapter import libname
import cas_bacnet_stack.CASBACnetStackAdapterBindings as bacnet
from common.simple_udp import SimpleUDP
from common import cas_example_helper

library = ctypes.CDLL(libname)
bacnet.bind(library)

udp = SimpleUDP()
udp.setup(port)
cas_example_helper.register_common_callbacks(udp, NETWORK_PORT_INSTANCE)  # before AddDevice
# ... AddDevice, objects, services ...
cas_example_helper.send_i_am(device_instance, port, NETWORK_PORT_INSTANCE)  # announce on start-up
while running:
    bacnet.BACnetStack_Tick()
    time.sleep(0.001)
```

Unlike the C++/C# `common/`, there is no `RestartKind`/`RequestRestart`/
`RestartDue` deferred-restart pattern here: B-SS does not implement DM-RD-B
(ReinitializeDevice), so this copy of `common/` does not carry code for a
capability no example using it needs yet. Add it back (port from a sibling
that has it, once one exists) if you build a Python profile example that
requires DM-RD-B.

## Why no netmask discovery

The C++/C# editions read the host's real subnet mask from the OS
(`getifaddrs()` / `System.Net.NetworkInformation.NetworkInterface`). The
Python standard library has no portable equivalent - a real one needs a
third-party package (`netifaces`, `psutil`, ...), and this example
deliberately stays dependency-free (stdlib only - see AGENTS.md). So
`get_local_ipv4()` in `cas_example_helper.py` learns the outbound IP via a
UDP "connect" trick and ASSUMES a /24 netmask. See that function's docstring
for the full explanation and why this is a documented simplification, not a
hidden bug.
