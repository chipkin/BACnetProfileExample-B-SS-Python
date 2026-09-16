# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - unreleased

### Added

- The **first B-SS (Smart Sensor) Python implementation** in this example
  series, and the first Python example in the series overall - ported from
  [BACnetProfileExample-B-SS-CPP](https://github.com/chipkin/BACnetProfileExample-B-SS-CPP)
  v1.2.0 and
  [BACnetProfileExample-B-SS-CS](https://github.com/chipkin/BACnetProfileExample-B-SS-CS)
  v1.0.0 (same device model, same object/property split between "app" and
  "stack", same section layout and documentation skeleton). The binding
  mechanism is new to this series: `ctypes` against the vendored
  `submodules/cas-bacnet-stack/adapters/python/` bindings, not the C++
  direct-link, the C# P/Invoke, or the Node N-API addon - see
  `common/CHANGELOG.md` for what that changes.
- The complete B-SS example application (`main.py`): device 389001
  ("Rainbow"), the series' three read-only input objects (Analog Input
  "Bronze", Binary Input "Emerald", Multi-State Input "Hot Pink") plus the
  required Network Port ("Vermilion"), DS-RP-B (ReadProperty), DM-DDB-B /
  DM-DOB-B (Who-Is/I-Am, Who-Has/I-Have), unsolicited I-Am on start-up,
  series-standard CLI (`--help`/`--version`/`--deviceID`/`--port` via
  `argparse`) and interactive keys (`h`/`q`/arrows - `msvcrt` on Windows,
  `termios`/`tty`/`select` on POSIX, skipped automatically when stdin is not
  a real console, e.g. the CI smoke test). There are no `Set*Property`
  callbacks and `SERVICE_WRITE_PROPERTY` is never enabled - this device is
  read-only end to end, matching the B-SS profile boundary.
- Vendored Python `common/` v1.0.0: `simple_udp.py`, `cas_example_helper.py`
  (transport callbacks + the 6-byte IPv4 connection string, I-Am, local-IP
  discovery, CLI validators), `cas_bacnet_stack_example_constants.py`. See
  `common/CHANGELOG.md` for the full list of what targeting the
  `submodules/cas-bacnet-stack` `6.x` branch's Python adapter means (trailing
  `errorCode` on every `Get*Property` callback, the folded
  `AddNetworkPortObject()`, the `*ForPort` transport callbacks keyed by
  Network Port instance, and - unique to Python - the explicit
  `ctypes.CDLL()` + `bind()` load step and callbacks rooted against CPython
  reference counting rather than a GC pause).
- Direct source inclusion of the vendored adapter's three files
  (`CASBACnetStackAdapter.py`, `CASBACnetStackAdapterBindings.py`,
  `property_buffer_helper.py`) into `cas_bacnet_stack/` - there is no PyPI
  package for this adapter; see `cas_bacnet_stack/README.md` for why this is
  a real, working adapter despite `CASBACnetStackAdapter.py`'s stale
  "HELPERS ONLY" docstring, and why `property_buffer_helper.py` is vendored
  but unused.
- Repository scaffold: CAS BACnet Stack submodule (`submodules/cas-bacnet-stack`,
  tracking `6.x`), CC0-1.0 licence, README, TUTORIAL, `docs/PICS.md` +
  `docs/objects.json`, AGENTS.md, changelog.

Verified on the wire: Who-Is → I-Am; every required property of every object
reads back; `State_Text[1..3]` reads `On`/`Off`/`Auto` and `State_Text[4]`
errors `invalid-array-index`; WriteProperty is rejected on every object (no
`Set*Property` callback registered).
