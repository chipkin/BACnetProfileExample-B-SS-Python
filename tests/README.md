# B-SS Wire Tests

Tests that drive the running smart sensor over BACnet/IP from outside it. A
B-SS device's Profile Function is to report what it measures to any client that
asks - ANSI/ASHRAE 135-2024 Annex L.4.5: "Ability to provide values for any of its
BACnet objects upon request". So the tests ask for everything, the way a client
discovering the device does; then ask again and again to see the readings follow
the sensor Simulation; then break the sensor and ask what is wrong with it. They are written against the series' shared harness in
[`../wiretest/`](../wiretest/README.md) (vendored, like `common/`); everything
specific to this sensor is here. Python 3 standard library only - nothing to
`pip install`.

## Running

These scripts are the C++ reference's (`BACnetProfileExample-B-SS-CPP`
`tests/`), run against this Python port. Build the CAS BACnet Stack library
(README "Build the CAS BACnet Stack library"), then from the repository root:

```bash
python tests/run_wire_tests.py
python tests/run_wire_tests.py --port 47824 --exe "python3.10 main.py"
```

`--exe` defaults to `main.py`; a path ending in `.py` is run with the Python
that runs the tests. It may also be a whole command line:
`bss_setup.launch_command()` splits it with `shlex` (a bare program name such as
`python3` is looked up on `PATH`) - the one change from the reference's
scripts, apart from naming `main.py` where they name `main.cpp`, and
`configuration_test.py`'s `--help` check, which names the options this port
reads (it has no `--xml`). It ends with
`ALL WIRE TESTS PASSED` (exit 0) or the scripts that failed. `--port` (default
47824) is the UDP port the test starts the sensor on. It takes about 25 seconds.
CI (`.github/workflows/release.yml`) runs it on Linux after the smoke test.

## The setup

```
test client (127.0.0.1, ephemeral UDP port)  - the Peer
    |  BACnet/IP, unicast
BACnetExampleBSS  UDP --port                 - Device 389001
```

The Peer is a Python BACnet client (`wiretest.Client`), never another example's
binary. It plays a BACnet client such as Chipkin BACnet Explorer, or a controller
polling the sensor. `bss_setup.py` holds what the scripts share: the object and
property numbers, the Simulation's rates (they match `main.py` section 2), and
starting the example.

A request unanswered after 0.6 s is sent again, up to 3 times
(`bss_setup.REQUEST_TIMEOUT` / `RETRIES`, what a BACnet client's
Number_Of_APDU_Retries does); each resend prints a `[RETRY]` line, so a lost
request shows in the output instead of being tolerated silently. A busy Windows
host loses the odd UDP datagram even on loopback, where an answer takes
milliseconds.

The one thing a test does to the example other than over BACnet is the
Simulation's test-only broken-wire hook: `failure_modes_test.py` starts the
example with `CAS_EXAMPLE_TEST_SENSOR_FAULT_FILE` naming a file in the temp
folder, and the sensor wire is broken for as long as that file exists.

## `discovery_test.py` - every listed property reads as a value

1. **Who-Is** (for 389001, unicast) -> the device's I-Am.
2. **Device `Object_List`** names exactly the Device, Analog Input 1, Binary
   Input 1, Multi-state Input 1 and Network Port 1. This is the control: a walk
   over nothing would pass.
3. For each object, **`Property_List`** reads, and a ReadProperty of every
   property it lists - plus `Object_Identifier`, `Object_Name`, `Object_Type`
   and `Property_List`, which cl. 12.1.1.4.1 leaves out of the list - returns a
   ComplexACK. An Error, Reject, Abort or no answer prints an `[UNREADABLE]` line
   and fails the check. 135-2024 cl. 12.1.1.4.1: Property_List holds "one
   property identifier for each property that exists within the object".
4. Network Port 1's **`IP_DNS_Server` (406)**, **`FD_BBMD_Address` (418)** and
   **`FD_Subscription_Lifetime` (419)** are each listed and read as a value - one
   check per issue (#20, #21, #22), the three reads Explorer 4.23.2.0 found
   failing.
5. Device **`Database_Revision`** reads 5: the stack starts it at 0 and adds one
   for each object added at start-up (the Device and its four objects), and
   nothing changes the object database afterwards (cl. 12.11; docs/PICS.md).

## `configuration_test.py` - the Device's identity is configurable

BACnet requires the Device's Object_Identifier and Object_Name to be
configurable (135-2024 cl. 12.1.1.3, 12.1.1.4); Object_Name must be unique
across the internetwork, so two units cannot share a compile-time name. The
sensor is started three ways, then asked for `--help`:

1. **No options (control):** Device 389001 answers Who-Is, and its
   `Object_Name` is the default `Chipkin Example B-SS`.
2. **`--deviceID 389901 --deviceName "Chipkin Example B-SS Unit 2"`:** the
   device answers Who-Is as 389901; `Object_Name` reads the configured name;
   a read of Device 389001 gets Error OBJECT / UNKNOWN_OBJECT (1/31); the
   ready line names the configured device; a Who-Has by the configured name
   gets an I-Have from Device 389901 with that name (DM-DOB-B).
3. **Boundaries:** an empty name and a 256-byte name each print a warning and
   keep the default; a 255-byte name (the limit) reads back whole.
4. **`--help`** lists `--port`, `--deviceID` and `--deviceName`, and neither
   `--dcc-password` (a B-SS has no DeviceCommunicationControl) nor `--xml`.

Mutation (2026-10-22, Windows): `get_property_character_string` serving the
constant `DEVICE_NAME` instead of the configured name fails 3 of 17 checks (the
configured name, the Who-Has, the 255-byte name).

## `sensing_test.py` - the readings follow the sensor (the Profile Function)

1. **Control:** Analog Input 1 `Units` is degrees Celsius; `State_Text` is
   On / Off / Auto.
2. Reads `Present_Value` of all three sensors every 0.5 s for 12 s (72 reads),
   every one a value.
3. **Analog Input 1** changes (at least 5 distinct readings), in whole 0.5 C
   steps and never more steps between two reads than the once-a-second tick
   allows (timed from the first read's request to the second's answer, so a
   retried read cannot fake a jump), at least 3.5 C of movement in total, never
   outside 18.0 .. 26.0.
4. **Binary Input 1** toggles (at least 3 changes) and holds each state for
   3 s (+/- 1 s).
5. **Multi-State Input 1** steps at least twice, each time to the next state
   (1 -> 2 -> 3 -> 1) - judged between reads less than one 4 s step apart -
   never outside 1..Number_Of_States.

A sensor that answers every read with a constant passes every check of
`discovery_test.py` and fails steps 3-5 here.

## `failure_modes_test.py` - a broken sensor, and requests it must refuse

1. **Control:** Reliability `no-fault-detected` (0), Status_Flags all FALSE, and
   the reading moves over 2.5 s.
2. **Break the wire** (create the fault file): within 3 s Reliability reads
   `open-loop` (4); Status_Flags is {FALSE, TRUE, FALSE, FALSE} - FAULT alone
   (12.2.7); read every 0.25 s for 2.5 s, the reading has one value; Binary Input 1 still answers,
   with Status_Flags all FALSE.
3. **Refusals** (15.5.1.3.1, 18.9): ReadProperty of Analog Input 99 -> Error
   OBJECT / UNKNOWN_OBJECT (1/31); of Analog Input 1 High_Limit -> Error
   PROPERTY / UNKNOWN_PROPERTY (2/32); of State_Text[4] -> Error PROPERTY /
   INVALID_ARRAY_INDEX (2/42); WriteProperty of Analog Input 1 Present_Value ->
   Reject UNRECOGNIZED_SERVICE (9), and the reading is not the written 99.0.
4. **Repair the wire** (delete the file): Reliability back to
   `no-fault-detected` within 3 s, Status_Flags all FALSE, the reading moves again.

## This port's mutation check

Run 2026-10-16 on Windows: one feature removed from `main.py` (its sha256
checked to have changed), the named script run, `main.py` restored. Every
mutation but the State_Text line is caught, exactly as in the reference's table
below:

| Feature removed (`main.py`) | Script | Fails with |
|---|---|---|
| `sensor_simulation_tick()` not called | sensing (6/11) | `Analog Input 1 changes between reads ... - read [21.5]`; BI `read [0]`; MSI `read [1]` |
| the wire never breaks (`sensor_wire_broken()` false) | failure_modes (11/14) | `Wire broken: Reliability reads OPEN_LOOP within 3 s - read 0 after 3.1 s`; `... Status_Flags FAULT is TRUE ... - read [False, False, False, False]`; `... no longer moves ... - read [24.0, 24.5, 25.0, 25.5]` |
| the Reliability branch of `get_property_enumerated` declines | failure_modes (12/14) | `Wire broken: Reliability reads OPEN_LOOP within 3 s - read 0 after 3.1 s`; Status_Flags FAULT FALSE |
| Binary Input 1 toggles every 1 s, not 3 s | sensing (10/11) | `... holding each state for about 3 s - held [1.0, 1.0, ...] s` |
| State_Text's own `invalid-array-index` line | failure_modes (14/14) | **survives**, as the reference's M9: the stack answers 2/42 itself |

The reference's own mutation table follows; its line numbers and names are the
C++ example's.

## Each check fails without its feature

Run 2026-10-16 on Windows (STATIC build, relinked each time - the binary's
mtime checked): one feature removed from `main.cpp`, rebuilt, the named script
run, the source restored. Every mutation but M9 / M9c is caught:

| # | Feature removed (`main.cpp`) | Script | Fails with |
|---|---|---|---|
| M1 | `SensorSimulationTick()` not called | sensing, failure_modes | `Analog Input 1 changes between reads ... - read [21.5]`; BI `read [0]`; MSI `read [1]`; `Control: the healthy reading moves - read 21.5 then 21.5` |
| M2 | Binary Input 1 serves a constant 0 | sensing | `Binary Input 1 toggles active / inactive ... - read [0]`; `... holding each state ... - held [] s` |
| M3 | Multi-State Input 1 serves a constant 1 | sensing | `Multi-State Input 1 steps to a new state at least twice - read [1]` |
| M4 | the temperature ramp line | sensing | `Analog Input 1 changes between reads ... - read [21.5]`; `... at the Simulation's rate ...` |
| M11 | ramp step 0.5 -> 1.0 C | sensing | `... in whole 0.5 C steps, no more than one step per second ...`; `... and inside 18.0 .. 26.0 C - read [... 26.5 ...]` |
| M12 | Binary Input 1 toggles every 1 s, not 3 s | sensing | `... holding each state for about 3 s - held [1.0, 1.0, ...] s` |
| M13 | Multi-State Input 1 steps backwards | sensing | `... each step to the next state (1 -> 2 -> 3 -> 1) ... - read [1, 3, 2]` |
| M5 | the wire never breaks (`SensorWireBroken()` false) | failure_modes | `Wire broken: Reliability reads OPEN_LOOP within 3 s - read 0`; `... Status_Flags FAULT is TRUE ... - read [False, False, False, False]`; `... no longer moves - read 24.0 then 25.5` |
| M6 | the reading keeps moving while broken | failure_modes | `Wire broken: the reading no longer moves (2.5 s apart) - read 23.0 then 24.0` |
| M7 | the fault latches (never repaired) | failure_modes | `Wire repaired: Reliability back to NO_FAULT_DETECTED within 3 s - read 4`; `... Status_Flags all FALSE again - read [False, True, False, False]`; `... moves again - read 22.5 then 22.5` |
| M8 | the Reliability branch of `GetPropertyEnumerated` declines | failure_modes | `Wire broken: Reliability reads OPEN_LOOP within 3 s - read 0`; `... Status_Flags FAULT is TRUE ... - read [False, False, False, False]` (the stack substitutes 0 = no-fault-detected, silently) |
| M10 | Reliability not enabled | failure_modes | `Control: a healthy sensor ... - read ('error', ...)`; `Wire broken: Reliability reads OPEN_LOOP ... - read error`; `... Status_Flags FAULT is TRUE ... - read [False, False, False, False]` |
| M15 | WriteProperty service enabled | failure_modes | `WriteProperty of Analog Input 1 Present_Value -> Reject UNRECOGNIZED_SERVICE ... - Error class=2 code=40` |
| M9 | State_Text's own `invalid-array-index` line | failure_modes | **survives**: the stack checks the index against the length `GetPropertyUnsignedInteger` serves for index 0 and answers 2/42 itself |
| M9c | State_Text length served as 4 | failure_modes | **survives**: the callback's own line answers 2/42 |
| M9b | both (length 4 and no line) | failure_modes | `ReadProperty of State_Text[4] (it has 3) -> Error PROPERTY / INVALID_ARRAY_INDEX - value=''` |

So the State_Text check gates the pair: either layer alone answers correctly
(M9, M9c), and without both the client silently gets an empty string (M9b).
The UNKNOWN_OBJECT and UNKNOWN_PROPERTY checks have no example code to remove:
they pin what the stack answers for this device, as clause 15.5.1.3.1 names it.


## `discovery_test.py` fails without the #20-#22 fix

The fix for #20-#22 is in the stack, so "without the fix" is the old Stack Pin.
Run 2026-10-15, the same `main.cpp`, stack `6.x` @ `abd4cee1` (6.0.21) against
`6.x` @ `64b2cfac5` (6.0.23):

| Stack | Windows (STATIC build) | Linux (WSL Ubuntu 22.04, SOURCE build) |
|---|---|---|
| `abd4cee1` | 7/11 - FAIL | 7/11 - FAIL |
| `64b2cfac5` | 11/11 - PASS | 11/11 - PASS |

At `abd4cee1`, on both platforms, the failures were exactly these three reads:

```
[UNREADABLE] Network Port 1 property 406: Abort reason=0
[UNREADABLE] Network Port 1 property 418: Error class=2 code=72
[UNREADABLE] Network Port 1 property 419: Error class=1 code=27
[FAIL] every property of every object reads as a value (74 reads) - 3 unreadable: Network Port 1 406, Network Port 1 418, Network Port 1 419
[FAIL] Network Port 1 IP_DNS_Server (406): listed in Property_List and reads as a value (issue #20) - Abort reason=0
[FAIL] Network Port 1 FD_BBMD_Address (418): listed in Property_List and reads as a value (issue #21) - Error class=2 code=72
[FAIL] Network Port 1 FD_Subscription_Lifetime (419): listed in Property_List and reads as a value (issue #22) - Error class=1 code=27
```

Abort reason 0 is `other`; Error class 2 code 72 is `property` /
`value-not-initialized`; class 1 code 27 is `object` / `read-access-denied` -
what Explorer reported. At `64b2cfac5` the walk is 78 reads, all values.
