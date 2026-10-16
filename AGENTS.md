# AGENTS.md

Guidance for AI coding agents working in this repository. See
<https://agents.md/> for the format. Human contributors should read
[README.md](README.md) first, then [TUTORIAL.md](TUTORIAL.md).

## What this project is

A **tutorial** Python example that implements the BACnet **B-SS** (Smart
Sensor) profile using the CAS BACnet Stack through `ctypes`: a minimal,
**read-only** BACnet/IP device (DS-RP-B, DM-DDB-B, DM-DOB-B) whose readings
follow a sensor **Simulation** and which reports a broken sensor as a fault.
It is one of a series - one git repo per BACnet profile and language - and the
**faithful Python translation of `BACnetProfileExample-B-SS-CPP`** (v1.3.0):
same Device, objects, properties, Simulation, Failure Modes, test-only hook,
command line and Wire Tests. A test cannot tell the two apart on the wire; keep
it that way. The top priority is that the code reads like a tutorial a customer
can learn from and copy-paste. Favour clarity over cleverness.

## Layout

- `main.py` - the whole application, four numbered sections like `main.cpp`
  (1 configuration, 2 the sensor Simulation, 3 the `get_property_*` callbacks,
  4 `main()`).
- `common/` - the shared Python helper (`simple_udp.py`,
  `cas_example_helper.py`, `cas_bacnet_stack_example_constants.py`), vendored
  in, with its own version (`COMMON_VERSION`) and `common/CHANGELOG.md`. It is
  the Python edition of the C++ `common/`; port C++ `common/` conventions into
  it, never the other way round.
- `tests/` - the Wire Tests, copied from the C++ reference. The only local
  change is `tests/bss_setup.py`'s `default_command()` / `launch_command()` /
  `start()` (so `--exe` can be `main.py` or a command line) and the file names
  in comments. Keep it that way: a new check goes into the reference first.
- `wiretest/` - the series' shared Wiretest Harness (0.7.0), **byte-identical**
  to `BACnetProfileExample-B-SS-CPP/wiretest/`. **Never edit it**; if it needs a
  change, report it.
- `README.md` - what this example is. Keep it short and about THIS example.
- `TUTORIAL.md` - how to extend and review the example.
- `docs/PICS.md` - the PICS. Its objects-and-properties section is GENERATED
  from `docs/objects.json`; do not hand-edit between the `OBJECTS-PROPERTIES`
  markers (the one exception: the generator's intro sentence names
  `main.cpp`'s `GetProperty*`; this repository says `main.py`'s
  `get_property_*`).
- `submodules/cas-bacnet-stack/` - the **CAS BACnet Stack** as a git submodule
  (private; Stack Pin `6.x` @ `64b2cfac5`, 6.0.23). After cloning, run
  `git submodule update --init --recursive`. Two things in it are used
  **in place**:
  - `adapters/python/` - the stack's Python adapter. `main.py` puts it on
    `sys.path`. `CASBACnetStackAdapterBindings.py` is **generated** by the
    stack's `ci_scripts/generate-python-adapter.js`. **Never copy, vendor,
    regenerate by hand or edit any adapter file into this repository** - it is
    part of the licensed stack. If it is missing something, put the smallest
    marked workaround in this repository's own code and report it as an
    adapter defect.
  - `bin/` - where the stack library is built (`CASBACnetStack_x64_Release.dll`
    / `libCASBACnetStack_x64_Release.so`) and where `main.py` loads it from.

The `PROFILE-TABLE` block in README.md is generated from the example-series
repository's `docs/profile-table.md`. Edit it there, not here.

## Build

No build step for Python. The stack library is built once from the submodule
into its `bin/` (README.md "Build the CAS BACnet Stack library"):

```bash
git submodule update --init --recursive
# Windows: MSBuild submodules/cas-bacnet-stack/projects/msvs/CASBACnetStack/CASBACnetStack.vcxproj -p:Configuration=ReleaseDll -p:Platform=x64
# Linux:   g++ -shared -fPIC -std=c++17 -O2 -I submodules/cas-bacnet-stack/source submodules/cas-bacnet-stack/source/*.cpp -o submodules/cas-bacnet-stack/bin/libCASBACnetStack_x64_Release.so
python -m py_compile main.py common/*.py tests/*.py
```

**The stack binary is never committed and never released.** `.gitignore`
covers every library name; `.github/workflows/release.yml` builds the library to
test, and refuses to upload any `.dll` / `.so` / `.lib` / `.a` / `.node`.
`git ls-files | grep -iE '\.(dll|so|node|lib|a)$'` must print nothing. Never
copy the library to the repository root.

No dependencies beyond the Python standard library - do not add a
`requirements.txt`.

## Run

```bash
python main.py [--port 47808] [--deviceID 389001]   # python3 on Linux
python main.py --version
```

Interactive keys: `h` help, `q` quit, up/down nudge the simulated Analog Input
1 reading. On a redirected stdin only `h` / `q` (that is how the Wire Tests stop
it).

## Conventions

- Device "Chipkin Example B-SS"; objects use the series' colour names; vendor
  id 389; Protocol_Revision 30 (the stack's).
- Implement **only** what the B-SS profile requires - but expose **every
  required property** of each object.
- The sensor readings come from the **Simulation** in `main.py` section 2
  (`sensor_simulation_tick()`); it is outside the BACnet Surface and labelled so
  in the README. Its broken-wire hook is test-only
  (`CAS_EXAMPLE_TEST_SENSOR_FAULT_FILE`, an environment variable naming a file)
  - never a command-line option or a menu key.
- **Read-only.** WriteProperty is never enabled and there is no
  `BACnetStack_RegisterCallbackSetProperty*` call.
- **Explicit library load**, like the C++ `LoadBACnetFunctions()`:
  `main()`'s `load_cas_bacnet_stack()` looks in the run directory (the folder of
  `main.py`), then `submodules/cas-bacnet-stack/bin/`, does `ctypes.CDLL` +
  `bind()` before any `BACnetStack_*` call. Nothing imports or loads the stack
  at module import time. Without it (or if `ctypes` cannot load it) the example
  prints the series' missing-library message
  (`helper.print_missing_stack_library()`, owner ruling 2b - do not reword it)
  to stderr and exits 1, never a traceback; `--help` / `--version` still work.
- Every `BACnetStack_*` setup call's return value is checked; a failure prints
  which call failed and `main()` returns 1.
- Every `Get*Property` callback ends with an `error_code` pointer. Leave it
  alone on a catch-all `return False`; set it only where this device knows the
  read is wrong (the `State_Text` branch).
- **Callbacks must be rooted.** Every `ctypes.CFUNCTYPE` object passed to a
  `BACnetStack_RegisterCallback*` call is appended to
  `cas_example_helper._callback_refs` first - never held only by a local.
  CPython frees an unrooted one at once, and the next call into it crashes.
- **The stack is single-threaded.** Nothing calls a `BACnetStack_*` function or
  touches the UDP socket from another thread. (`common/`'s piped-stdin reader
  thread on Windows only queues key presses.)
- The 6-byte IPv4 connection string (4 octets + big-endian port) is packed in
  `common/cas_example_helper.py` only.
- Links are identified by **Network Port object instance**
  (`NETWORK_PORT_INSTANCE`).
- Present tense only: no comment or doc references a previous version.
- Never edit `common/` in this repo alone once a sibling Python example exists:
  bump `COMMON_VERSION`, add a `common/CHANGELOG.md` entry, sweep it.

## How to verify a change

1. `python -m py_compile main.py common/*.py tests/*.py`.
2. The Wire Tests (README "Wire Tests"):
   `python tests/run_wire_tests.py --port <n>` - discovery, the readings
   following the Simulation, and the Failure Modes. It must end
   `ALL WIRE TESTS PASSED`. A new check must fail with its feature removed
   (tests/README.md has the mutation tables).
3. If you changed the objects or their properties, update `docs/objects.json`
   and regenerate `docs/PICS.md` (`python tools/gen-objects-properties.py
   BACnetProfileExample-B-SS-Python` from the series root, then restore the
   `main.py` wording of its intro sentence); no row may be flagged with ⚠.

## Releasing

Bump `APP_VERSION` in `main.py` and add an entry to
[CHANGELOG.md](CHANGELOG.md), then tag `vX.Y.Z`. The GitHub Actions workflow
builds the stack library, smoke-tests and Wire-Tests the example, checks the
packaged app prints the missing-library message without the stack, and
publishes the example's own files (never the stack library or adapter).

## License

See [LICENSE](LICENSE). The CAS BACnet Stack, its adapters included, is a
separate, commercially licensed product and is not covered by it.
