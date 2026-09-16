# Tutorial - extending and reviewing the B-SS example

[README.md](README.md) says what this example *is*. This document is the
*how*: how to extend it into your own device, who serves which property, how
to review the result for conformance, and what goes wrong when you get it
subtly right.

Read this once before you start changing `main.py`. The most expensive
mistake in this example is silent, and the section it lives in is
[Add a second analog input](#add-a-second-analog-input).

- [Extending the example](#extending-the-example)
- [What each object type needs you to serve](#what-each-object-type-needs-you-to-serve)
- [Who serves what: the application or the stack?](#who-serves-what-the-application-or-the-stack)
- [Interactive keys are a simplification](#interactive-keys-are-a-simplification)
- [Reviewing your device](#reviewing-your-device)
- [Troubleshooting](#troubleshooting)

## Extending the example

The example is intentionally small so it's easy to change.

**Change a sensor's value or name** - edit the constants / callbacks in
`main.py` (e.g. `g_analog_input_1_value`, or the `"Bronze"` string in
`get_property_character_string`).

**Change the device identity before you ship** - vendor ID, vendor name,
model name, description, firmware revision and device name are all in the
`CHANGE ALL OF THIS BEFORE YOU SHIP` block at the top of `main.py` §1, with
a per-field note on each saying what to change it to. That block is the
authoritative checklist; it is in the source rather than here so it cannot be
skipped by someone who only reads the code. Keep the application-owned socket
+ `cas_example_helper.register_common_callbacks()` shape, the habit of
checking every `BACnetStack_*` return value, and the
callbacks-rooted-in-a-module-level-list pattern - those are part of the
shape, not the identity, and every sibling example (C++ or C#) keeps the
first two of those too.

### Add a second analog input

Read this whole recipe before starting - the last step is the one that is
easy to miss and the one BTL will fail you for.

> **Why there are four edits, not three - and why skipping one is SILENT.**
> Most of the `get_property_*` callbacks match on **both** object type *and*
> instance (`object_instance == ANALOG_INPUT_INSTANCE`), so a new instance
> falls through every one of them. `get_property_bool`'s `Out_Of_Service`
> branch is the exception: it matches on `property_identifier` (and
> `object_type`) alone, so `Out_Of_Service` works for a new instance for
> free.
>
> Here is the part that matters, and it is the opposite of what most people
> assume. Falling through a callback does **not** reliably produce an error.
> The stack errors only for the few properties it refuses to invent -
> `Present_Value`, `Number_Of_States`, `Relinquish_Default`, `Local_Date`,
> `Local_Time`, and a Network Port's `APDU_Length`. For everything else it
> **silently substitutes a default**:
>
> | Property | If you forget to serve it | Loud? |
> |---|---|:--:|
> | `Present_Value` | Error (`value-not-initialized`) | yes |
> | `Object_Name` | reads back as the literal string **`"undefined"`** | **no** |
> | `Units` | reads back as **`no-units` (95)** | **no** |
> | `Out_Of_Service` | served on property + type alone - works by accident | n/a |
>
> **Doesn't the `errorCode` out-parameter fix this?** Only if you use it, and
> only where it is right to. Each `get_property_*` callback receives a
> trailing `errorCode` pointer that the stack pre-seeds with `success` and
> reads only when you return `False`, so you *can* turn any decline into a
> chosen BACnet error. But writing an error code on the catch-all breaks the
> device: the stack's decline-and-fabricate path is what answers required
> properties an application is not expected to serve - the Device's
> `Max_APDU_Length_Accepted`, `APDU_Timeout` and `Number_Of_APDU_Retries`
> among them. Write `error_code[0]` only where *this device* knows the read
> is wrong; `main.py` does it in exactly one place - `State_Text` with an
> out-of-range array index
> (`cas_bacnet_stack_example_constants.ERROR_CODE_INVALID_ARRAY_INDEX`).
>
> It is worse than "wrong value": the object's `Property_List` **still
> advertises `Units` (117)**. So the object actively claims to have the
> property, and then answers with a default. Nothing on the wire says you
> forgot anything.
>
> So a half-added object does not look broken; it looks **healthy**. Add two
> of them and both report `Object_Name "undefined"` - duplicate object names
> inside one device, which is a spec violation and a hard BTL failure that
> every scan tool will render as a perfectly good object. **"It scanned OK"
> is exactly the failure mode, not evidence against it.**

```python
# 1) a new instance number (in §1 Configuration).
#    Naming: a second object of a type is "<Colour> 2" - so Analog Input 2 is
#    "Bronze 2", NOT a new colour. Each object TYPE owns one colour series-wide.
ANALOG_INPUT_2_INSTANCE = 2  # "Bronze 2"
g_analog_input_2_value = 23.1  # its live value

# 2) add the object (in main(), next to the other BACnetStack_AddObject calls).
#    Check the return, like every other stack call in this file.
if not bacnet.BACnetStack_AddObject(g_device_instance, c.OBJECT_TYPE_ANALOG_INPUT, ANALOG_INPUT_2_INSTANCE):
    print("Error: Failed to add Analog Input 2 (Bronze 2).")
    return 1

# 3) serve its Present_Value + Object_Name:
#    get_property_real:              AI/2 + Present_Value -> value[0] = g_analog_input_2_value
#    get_property_character_string:  AI/2 + Object_Name    -> _return_character_string("Bronze 2", ...)

# 4) DO NOT SKIP: serve its Units, in get_property_enumerated.
#    Units is a REQUIRED property of an Analog Input. The existing check reads
#    `object_instance == ANALOG_INPUT_INSTANCE`, which is instance 1 - so
#    without this, reading Analog Input 2's Units returns no-units(95) instead
#    of erroring, and the object is NON-CONFORMANT. It will still appear in
#    Object_List and its Present_Value will read back perfectly, so the device
#    looks healthy right up until BTL certification.
#    get_property_enumerated: AI/2 + Units -> value[0] = c.ENGINEERING_UNITS_DEGREES_CELSIUS
```

Then re-run the README's Verify steps **against Analog Input 2**, not just
Analog Input 1 - read every required property and **diff it against Analog
Input 1**. Any property that comes back `"undefined"`, `no-units`, or `0`
where object 1 returns something real is a step you missed. Because the
failure is silent (see the table above), this diff is the only thing that
catches it.

### Who serves what: applying it to a new object

There is no commandable-output section in this tutorial - **B-SS has no
outputs**: every object in this profile is a read-only input, so there is no
priority array, no `Relinquish_Default`, no `Set*Property` callback anywhere
in `main.py`. If you need a commandable object (Analog Output, Binary
Output, Multi-State Output, or a Value object with `Priority_Array`
enabled), that is a *different* profile (B-SA or B-ASC) - see the C++ or C#
editions of the example series for the commandable-output model
(`Commandable`, `CommandWrite`, `CommandRelinquish`) and the
`Set*Property` callback shape it requires (there is no Python edition of
that example yet - port the shape using this example's `ctypes` conventions).
Bolting that model onto this example without also enabling `WriteProperty`
(`SERVICE_WRITE_PROPERTY`) and the object's
`Priority_Array`/`Relinquish_Default` properties would not make the object
writable anyway - review
[§4 Application services supported](docs/PICS.md#4-application-services-supported)
in the PICS before you reach for it.

The recipe that *is* relevant to a Smart Sensor - adding another read-only
input of a **different** type - follows the same four-step shape as
[Add a second analog input](#add-a-second-analog-input) above: a new instance
number, `BACnetStack_AddObject`, `Object_Name` + the type's other required
value property (`Polarity` for a Binary Input, `Number_Of_States` for a
Multi-State Input), and a diff against the existing object of that type.

## What each object type needs you to serve

The application must serve every REQUIRED property the stack does not
generate. It differs per type - this is the checklist, so you do not have to
infer it:

| Object type | You must serve | Plus |
|---|---|---|
| Analog Input | `Present_Value` (Real), `Object_Name`, `Units` | `Out_Of_Service` |
| Binary Input | `Present_Value` (Enumerated), `Object_Name` | `Polarity`, `Out_Of_Service` |
| Multi-State Input | `Present_Value` (Unsigned), `Object_Name` | `Number_Of_States`, `Out_Of_Service` |

`Out_Of_Service` is served once, in `get_property_bool`, matched on
`property_identifier` alone across all three input types plus the Network
Port - it is the one callback in this file that does NOT also match on
object type/instance, which is exactly why it is safe to leave unmatched: a
read-only sensor is never out of service, so the answer is always `False`.

## Who serves what: the application or the stack?

The single most common question when reading this file is "who answers this
property?" For Analog Input 1, the whole picture:

| Property | Served by | How |
|---|---|---|
| `Object_Identifier` | **stack** | generated from the object you added |
| `Object_Type` | **stack** | generated |
| `Object_List` | **stack** | generated (Device object) |
| `Property_List` | **stack** | generated |
| `Status_Flags` | **stack** | generated |
| `Event_State` | **stack**, sort of | no intrinsic alarming here, so nothing serves it - it reads `normal` only because `normal` is the enumeration's zero value and the stack substitutes a datatype default. Correct by coincidence, not design. |
| `Out_Of_Service` | **you** | `get_property_bool` - matched on property (+ type) only |
| `Present_Value` | **you** | `get_property_real` |
| `Object_Name` | **you** | `get_property_character_string` |
| `Units` | **you** | `get_property_enumerated` |

Every object, not just this one, is in [docs/PICS.md](docs/PICS.md).

Two more traps worth calling out explicitly, both silent:

- **Two `networkType`/`networkPortInstance` identifiers, easy to confuse.**
  The Network Port object's `NETWORK_PORT_NETWORK_TYPE_IPV4` (5, a *property*
  enumeration passed to `BACnetStack_AddNetworkPortObject`) is a *different*
  thing from the *link* identifier every transport call and `SendIAm` use -
  the Network Port object's own **instance** (`NETWORK_PORT_INSTANCE`, 1 in
  this example), which `common/cas_example_helper.py`'s
  `register_common_callbacks()` and `send_i_am()` both take as a parameter.
  Mixing them up runs without a Python exception (both are plain integers)
  and can silently misroute a multi-port device; a single-port example like
  this one is forgiving of the mistake, which is exactly why it is worth
  naming.
- **The stack's own errorCode default is NOT "no error."**
  `get_property_character_string`'s `State_Text` branch is the one place
  this file writes `error_code[0]` - it is pre-seeded with `success`, so a
  `return False` there without setting it would put "Error Class PROPERTY,
  Error Code success" on the wire instead of `invalid-array-index`. Every
  other `return False` in this file leaves `error_code` untouched on purpose
  (see the callout in [Add a second analog input](#add-a-second-analog-input)
  above).

Going beyond this (WriteProperty, COV, alarms, scheduling) means implementing
a richer profile - see the series table in [README.md](README.md).

## Interactive keys are a simplification

The C++ edition polls raw console keys (including arrow-key escape
sequences) every millisecond in its own `while` loop. The C# edition uses
.NET's built-in non-blocking `Console.KeyAvailable` + `Console.ReadKey(true)`.
Python has no single stdlib mechanism that works identically cross-platform,
so `main.py` picks per-OS: `msvcrt.kbhit()`/`getch()` on Windows (a direct
poll, no escape-sequence decoding needed - `msvcrt` already reports arrow
keys as a two-byte prefix + code), and `termios`/`tty.setcbreak()` +
`select.select(..., timeout=0)` on POSIX (put the terminal into cbreak mode,
poll non-blocking, and hand-decode the `ESC [ A`/`ESC [ B` arrow-key escape
sequence - closer to the C++ edition's approach there).

The one thing this approach cannot do is read keys when stdin is **not** a
real, non-redirected console (a background process, a CI smoke test, output
piped to a file): `main.py` checks `sys.stdin.isatty()` once at start-up and
skips key polling entirely when it is false - the device still runs
(`BACnetStack_Tick()` keeps ticking, and Ctrl+C/SIGTERM still work via the
`signal.signal()` handlers registered in `main()`), it just cannot be nudged
from the keyboard. This mirrors the C# edition's `Console.IsInputRedirected`
check and the CI smoke test in `.github/workflows/release.yml`, which never
touches the keyboard.

## Reviewing your device

After you have changed anything, review it against the conformance statement
rather than against "it looked fine in the explorer":

1. Regenerate [docs/PICS.md](docs/PICS.md) after editing `docs/objects.json`
   (see [Keeping the PICS honest](#keeping-the-pics-honest) below). A ⚠ row is
   a required property nothing serves.
2. Read **every** property listed for **every** object with a BACnet client,
   and compare the value against the PICS. `"undefined"`, `no-units` and `0`
   are the three shapes a missed callback takes.
3. Diff a new object of a type against the existing one of that type. Anything
   that differs and shouldn't is a callback that matched on instance.
4. Send a **WriteProperty** to any object and confirm it is rejected - a B-SS
   Smart Sensor is read-only, and this example never registers a
   `Set*Property` callback, so the stack has nothing to consult and declines
   on its own.
5. Read `State_Text[4]` on Multi-State Input 1 (which only has 3 states) and
   confirm `invalid-array-index`, not an empty string.

### Keeping the PICS honest

`docs/PICS.md` is partly generated. `docs/objects.json` describes each object
and who serves which property; the series tool regenerates the object tables
from it plus the stack's own `docs/property-profile-reference.md` at the
pinned commit:

```bash
python3 tools/gen-objects-properties.py BACnetProfileExample-B-SS-Python            # rewrite
python3 tools/gen-objects-properties.py BACnetProfileExample-B-SS-Python --check    # fail if stale
```

(That tool lives in the example-series repository, not in this one. If you
only have this repository, edit the generated block by hand and keep it
matching the callbacks in `main.py`.)

When you add an object or a property to `main.py`, update
`docs/objects.json` in the same change and regenerate. The `app` list is what
the callbacks serve; `accepted` is for a required property you deliberately
leave to the stack's default, and each one needs a justification. Anything
required, not in `app` and not in `accepted`, comes out as a ⚠ row - that is a
defect, not a feature.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `OSError: [WinError 126] The specified module could not be found` (or `OSError: ... cannot open shared object file`) from `ctypes.CDLL(...)` | The native library is missing from `main.py`'s directory (or the OS library search path). See README.md [Build the native CAS BACnet Stack library](README.md#build-the-native-cas-bacnet-stack-library) - it is a separate step from running `main.py`. |
| `OSError` mentioning a mismatched architecture (`%1 is not a valid Win32 application`, or similar on Linux) | The native library's architecture does not match this Python interpreter's. This example expects an x64 build - make sure both your Python interpreter and the DLL/.so you built are x64. |
| `AttributeError: function 'BACnetStack_...' not found` from `bind()` | The vendored `cas_bacnet_stack/CASBACnetStackAdapterBindings.py` and the native library are different stack versions. Re-copy `cas_bacnet_stack/` from the submodule's current `adapters/python/` and rebuild the native library from the same submodule commit. |
| App prints *"could not bind UDP port 47808"* | Another BACnet program is already using 47808. Stop it, or run with `--port <n>`. |
| Client sends Who-Is but sees no I-Am | Firewall is blocking UDP 47808, or the client and device are on different subnets (Who-Is is a broadcast). Allow the port; test on the same subnet first. |
| A WriteProperty you sent is rejected | Correct behaviour - this device is read-only. There is no `BACnetStack_RegisterCallbackSetProperty*` call anywhere in `main.py`; the stack declines every write without consulting the application. |
| The process crashes with no Python traceback, sometime after start-up | Almost always an unrooted `ctypes.CFUNCTYPE` callback that was garbage-collected. Grep your changes for `CFUNCTYPE(` and confirm every result is appended to a module-level list before being passed to a `RegisterCallback*` call - see AGENTS.md's callback-rooting rule. |
