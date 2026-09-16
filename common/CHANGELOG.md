# Changelog - `common/` (Python edition)

All notable changes to the vendored Python `common/` helpers. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-09-16

### Added

- `simple_udp.py` - application-owned UDP socket. Poll-based:
  `recv()` calls `socket.recvfrom()` on a non-blocking socket and catches
  `BlockingIOError`, so the whole class stays single-threaded, matching the
  C++/C# editions' model.
- `cas_example_helper.py` - `register_common_callbacks()` (receive/send/
  system-time callbacks; the 6-byte IPv4 connection string - 4 octets +
  big-endian port - packed/unpacked here once), `send_i_am()` targeting the
  local subnet broadcast, `get_local_ipv4()` (stdlib `socket`-only - see its
  docstring for the netmask-guessing deviation from the C++/C# editions),
  and CLI validators (`parse_port`, `parse_device_id`) for use with
  `argparse`.
- `cas_bacnet_stack_example_constants.py` - only the handful of BACnet
  enumeration values this example needs that are not already convenient to
  read out of `cas_bacnet_stack.CASBACnetStackAdapter`'s `bacnet_*`
  dictionaries; spelled out as named constants so the file diffs 1:1 against
  the C++/C# editions' `CASBACnetStackExampleConstants.*`.

### First Python `common/` in this series - what makes it different from the C++/C# editions

This is the first Python `common/` in the BACnet profile example series, so
there is no prior Python pin to diff against. The systematic differences
versus the C++ and C# editions:

- **Explicit library load, like C++ - unlike C#.** `main.py` calls
  `ctypes.CDLL(libname)` then `bacnet.bind(library)` itself, before any
  `BACnetStack_*` call - closer to the C++ edition's `LoadBACnetFunctions()`
  step than the C# edition's implicit first-P/Invoke-call resolution. A
  missing/wrong-architecture native library fails as an `OSError` from
  `ctypes.CDLL()`, at a point the application controls and can report
  clearly - see `main.py`'s startup sequence.
- **ctypes arrays as out-parameters, not managed buffers or raw pointers.**
  Every `Get*Property` callback in `main.py` receives ctypes `POINTER`
  objects it indexes like Python sequences (`value[0] = 21.5`,
  `for i in range(count): value[i] = ...`) - a middle ground between C#'s raw
  `byte*`/`uint*` pointers (same idea, different syntax) and a
  hypothetical managed-buffer marshaling layer (which this adapter does not
  provide).
- **Callbacks must be rooted, for a DIFFERENT reason than C#'s GC.** The
  CLR can collect an unrooted delegate; CPython's reference counting means a
  `ctypes.CFUNCTYPE`-wrapped callback is freed the moment nothing references
  it any more (no GC pause needed to trigger the bug - it can happen on the
  very next line). Every callback this file registers is appended to the
  module-level `_callback_refs` list for exactly that reason - see the
  comment at the top of `cas_example_helper.py`.
- **No netmask discovery.** The C++/C# editions read the real subnet mask
  from the OS (`getifaddrs` / `NetworkInterface`). The Python standard
  library has no portable equivalent without a third-party package (this
  example stays stdlib-only), so `get_local_ipv4()` guesses a /24 - see its
  docstring for the full explanation and the production caveat.
