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
lineage. This copy is **1.2.0**, built against the
`submodules/cas-bacnet-stack` Stack Pin (`6.x` @ `64b2cfac5`) and its Python
adapter, which it imports in place from the submodule's `adapters/python/`
(`main.py` puts that folder on `sys.path`; no adapter file is copied into this
repository). It follows the C++ `common/` 3.4.0 conventions a single-port
example uses. See `common/CHANGELOG.md` for what's in it and how the Python
binding mechanism differs from the C++/C# editions.

## What's here

| File | What it is |
|---|---|
| `simple_udp.py` | The UDP socket the application owns: bind, poll for inbound datagrams (non-blocking `recvfrom()`, no background thread), send. The stack never touches the socket - it pulls datagrams through the receive callback. |
| `cas_example_helper.py` | `setup_udp()` and `register_common_callbacks()` (receive/send/system-time + the 6-byte IPv4 connection string, port big-endian, written here ONCE; an RX / TX console line per datagram; a length-0 connection string, or a broadcast addressed to this socket itself, goes to the local subnet broadcast), `send_i_am()`, `get_local_ipv4()`, the command line (`handle_help_and_version_args()`, `parse_port_arg()`, `parse_device_id_arg()`, `parse_device_name_arg()` for `--deviceName`), the version banner (`print_version()`, with `COMMON_VERSION`) and the keys (`poll_key()`, `print_help()`, `restore_input()`). |
| `cas_bacnet_stack_example_constants.py` | The handful of BACnet enumeration values this example needs, spelled out as named constants so this file diffs 1:1 against the C++/C# editions' equivalents. |

## How main.py uses it

```python
import ctypes, os, sys
CAS_BACNET_STACK = os.path.join(REPOSITORY, "submodules", "cas-bacnet-stack")
sys.path.insert(0, os.path.join(CAS_BACNET_STACK, "adapters", "python"))  # the adapter, in place
from CASBACnetStackAdapter import libname
import CASBACnetStackAdapterBindings as bacnet
from common.simple_udp import SimpleUDP
from common import cas_example_helper as helper

bacnet.bind(ctypes.CDLL(library_path))  # main.py: the run directory, then <submodule>/bin
# (not found: helper.print_missing_stack_library(libname, folders); exit 1)
if helper.handle_help_and_version_args(sys.argv, APP_NAME, APP_VERSION):
    sys.exit(0)
port = helper.parse_port_arg(sys.argv, 47808)

udp = SimpleUDP()
helper.setup_udp(udp, port, NETWORK_PORT_INSTANCE)
helper.register_common_callbacks(udp, NETWORK_PORT_INSTANCE)  # before AddDevice
# ... AddDevice, objects, services ...
helper.send_i_am(device_instance, port, NETWORK_PORT_INSTANCE)  # announce on start-up
while running:
    bacnet.BACnetStack_Tick()
    if helper.poll_key() == helper.KeyCommand.QUIT:
        running = False
    time.sleep(0.001)
helper.restore_input()
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
