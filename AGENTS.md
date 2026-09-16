# AGENTS.md

Guidance for AI coding agents working in this repository. See
<https://agents.md/> for the format. Human contributors should read
[README.md](README.md) first, then [TUTORIAL.md](TUTORIAL.md).

## What this project is

A **tutorial** Python example that implements the BACnet **B-SS** (Smart
Sensor) profile using the CAS BACnet Stack's Python `ctypes` adapter: a
complete minimal, **read-only** BACnet/IP device (DS-RP-B, DM-DDB-B,
DM-DOB-B). Part of the BACnet profile example series, and the **first
Python example** in it - the C++ sibling is `BACnetProfileExample-B-SS-CPP`
and the C# sibling is `BACnetProfileExample-B-SS-CS`; this example keeps the
same objects, names, and section layout as both, but the binding mechanism is
new: `ctypes` against a vendored, generated adapter, not an embedded C++ link
or P/Invoke. The top priority is that the code reads like a tutorial a
customer can learn from and copy-paste. Favour clarity over cleverness.

## Layout

This repository is self-contained:

- `main.py` - the whole application, four numbered sections (§1
  configuration, §2 get callbacks, §3 interactive keys, §4 main). There is no
  §2b/§2c - a B-SS registers no `Set*Property` callback and no
  `DeviceCommunicationControl` handler.
- `common/` - the shared Python helper (`simple_udp.py`,
  `cas_example_helper.py`, `cas_bacnet_stack_example_constants.py`), vendored
  in. Never edit here alone: once a second Python example exists, a change
  must be swept to it too and `COMMON_VERSION` bumped with a
  `common/CHANGELOG.md` entry.
- `cas_bacnet_stack/` - the vendored Python adapter, copied verbatim from
  `submodules/cas-bacnet-stack/adapters/python/`. **Never edit these three
  files** - see `cas_bacnet_stack/README.md`.
- `README.md` - what this example is. Keep it short and about THIS example
  only.
- `TUTORIAL.md` - how to extend and review the example. Long-form material
  that would bloat the README belongs here.
- `docs/PICS.md` - the Protocol Implementation Conformance Statement. Its
  objects-and-properties section is GENERATED from `docs/objects.json`; do
  not hand-edit between the `OBJECTS-PROPERTIES` markers.
- `docs/objects.json` - the input to that generator. Update it in the same
  change as any `main.py` change that adds an object or a `get_property_*`
  branch.
- `submodules/cas-bacnet-stack` - the **CAS BACnet Stack** as a git submodule
  (private; tracks `6.x`). Its `adapters/python/` is the source this
  example's `cas_bacnet_stack/` is copied from; its `source/`/MSVC build
  produce the separately-built native shared library this example loads via
  `ctypes.CDLL()` at run time - see README.md "Build the native CAS BACnet
  Stack library". After cloning, run `git submodule update --init --recursive`.

The `PROFILE-TABLE` block in README.md is also generated, from the
example-series repository's `docs/profile-table.md`. Edit it there, not here.

## Build

There is no build step - Python is interpreted:

```bash
git submodule update --init --recursive   # once, if not cloned with --recursive
python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('.').rglob('*.py') if 'submodules' not in p.parts]"
                                           # optional compile-check (no separate "build" for a script)
```

This project has **no dependencies beyond the Python standard library** - do
not add a `requirements.txt` unless you also add a real third-party
dependency (and think hard before doing that; see `common/README.md`'s "Why
no netmask discovery" for why this example accepted a limitation instead of
reaching for `netifaces`/`psutil`).

Python itself does **not** build the native CAS BACnet Stack library that
`ctypes.CDLL()` loads - that is a separate native C++ build (MSBuild on
Windows against `submodules/cas-bacnet-stack/projects/msvs/BuildCASBACnetStack.sln`
`/p:Configuration=ReleaseDll /p:Platform=x64`; g++ on Linux). See README.md
for the exact commands.

## Run

```bash
python3 main.py --port 47821 --deviceID 12345   # run
python3 main.py --version                        # print versions and exit
```

Interactive keys while running (only when stdin is a real console - see
TUTORIAL.md "Interactive keys are a simplification"): `h` help, `q` quit,
up/down nudge Analog Input 1.

## Conventions

- Device is named "Rainbow"; objects use the series' colour names; vendor id
  389.
- Implement **only** the services and objects the B-SS profile requires -
  but expose **every required property** of each object.
- **This device is read-only.** There is no
  `BACnetStack_RegisterCallbackSetProperty*` call and
  `SERVICE_WRITE_PROPERTY` is never enabled anywhere in `main.py`; do not add
  Set-side plumbing here - that belongs in a different profile example
  (B-SA/B-ASC).
- **Explicit library load.** `main.py` calls `ctypes.CDLL(libname)` then
  `bacnet.bind(library)` itself, before any `BACnetStack_*` call - like the
  C++ edition's `LoadBACnetFunctions()`, unlike the C# edition's implicit
  first-P/Invoke-call resolution. A missing/wrong-architecture native library
  fails as `OSError`, caught and reported in `main()` before any socket is
  bound.
- Every `BACnetStack_*` setup call's return value is checked; failures print
  which call failed and exit non-zero (`sys.exit(1)` via `main()`'s return
  value).
- The stack PULLS: callbacks serve values through `ctypes` `POINTER`
  out-parameters, indexed like a Python sequence (`value[0] = 21.5`,
  `for i in range(count): value[i] = ...`), not managed buffers or C#-style
  raw pointer syntax. Every `Get*Property` callback ends with a trailing
  `errorCode` pointer out-param (stack issue #974) - leave it alone on a
  catch-all `return False`; set it only where this device knows the read is
  wrong (see the `State_Text` branch in `get_property_character_string`).
- Every `ctypes.CFUNCTYPE`-wrapped callback passed to a
  `BACnetStack_RegisterCallback*` call is appended to a module-level list
  (`cas_example_helper._callback_refs` for the transport/time callbacks,
  the equivalent list in `main.py` for the property callbacks) - **never**
  left rooted only by a local variable. CPython's reference counting frees an
  unrooted `CFUNCTYPE` object as soon as nothing references it, which is a
  crash at the stack's NEXT call into it, not a GC-pause-timed one - verify
  this with a grep of your own changes before finishing (`grep -n
  "CFUNCTYPE(" main.py common/*.py`, then confirm every match's result is
  appended somewhere before it is registered).
- The 6-byte IPv4 connection string (4 octets + BIG-endian port) is packed in
  `common/cas_example_helper.py` only - never re-derive it.
- Links are identified by **Network Port object instance**, not by a
  transport-type enumeration: `register_common_callbacks()` and
  `send_i_am()` both take a `network_port_instance` parameter, and the
  transport callbacks are `BACnetStack_RegisterCallbackReceiveMessageForPort()`
  / `BACnetStack_RegisterCallbackSendMessageForPort()`.
- Reuse enumeration values already defined in the vendored adapter
  (`cas_bacnet_stack.CASBACnetStackAdapter.bacnet_objectType`,
  `bacnet_propertyIdentifier`, ...) where convenient; this example instead
  spells out named constants in
  `common/cas_bacnet_stack_example_constants.py` for a 1:1 diff against the
  C++/C# editions - keep new constants there, not scattered through
  `main.py`.
- **The stack is single-threaded by contract.** Nothing in this codebase
  spawns a thread that calls a `BACnetStack_*` function or touches the UDP
  socket; all I/O is done through `common/simple_udp.py`'s non-blocking
  socket, polled once per `BACnetStack_Tick()` inside `main.py`'s own loop.
  Do not "fix" perceived latency by adding threading here.
- Present tense only: no comment or doc references a previous version of this
  example or of the stack.
- **Never edit `common/` in this repo alone once a sibling Python example
  exists** - it will be a vendored copy shared across the series, with its
  own version (`COMMON_VERSION`) and changelog (`common/CHANGELOG.md`).
- **Never edit `cas_bacnet_stack/`** - it is a verbatim copy of the
  submodule's `adapters/python/`. A fix belongs upstream.

## How to verify a change

There are no unit tests; verification is behavioural:

1. `python3 -m py_compile main.py common/*.py` (or the AST-parse one-liner
   above) with 0 errors.
2. Smoke: with the native library built and copied next to `main.py` (see
   README.md), `python3 main.py --port 47821` stays up past the ready banner
   (every failed setup call exits 1, so "still running" proves registration).
3. Read back what you changed with a BACnet client (Who-Is, ReadProperty of
   every required property; confirm a WriteProperty is rejected).
4. If you changed the objects or their properties, regenerate
   `docs/PICS.md` (`python3 tools/gen-objects-properties.py
   BACnetProfileExample-B-SS-Python` from the series root) and confirm no row
   comes out flagged with ⚠.

## Releasing

Bump `APP_VERSION` in `main.py` and add an entry to
[CHANGELOG.md](CHANGELOG.md), then tag `vX.Y.Z`. The GitHub Actions workflow
builds the native library, smoke-tests the Python script, and publishes a
release.

## License

See [LICENSE](LICENSE). The CAS BACnet Stack is a separate, commercially
licensed product and is not covered by it.
