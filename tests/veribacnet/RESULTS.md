# VeriBACnet results

The latest VeriBACnet run of this folder's project, summarised by hand from
that run's `report.json`. The run's own Results Folder (reports, packet
captures, wire logs) is not published: it holds the testing machine's network
addresses.

| | |
|---|---|
| Date | 2026-10-27 |
| Example | BACnet B-SS (Smart Sensor) Example - Python v1.1.0 build carrying the changes released in 1.2.0, built on CAS BACnet Stack 6.x @ 69b6249f |
| Profile | B-SS (BACnet Smart Sensor) |
| Transport | BACnet/IP, UDP port 47824 |
| VeriBACnet | 0.20.0 (its test device uses CAS BACnet Stack 6.0.23.0) |
| Test plan | 43 BTL tests (ANSI/ASHRAE 135.1-2023) selected for the B-SS profile |
| Result | **34 PASS · 0 FAIL · 0 ERROR · 9 SKIP** |

**Judged BTL-clean on BACnet/IP.** No test failed and none ended in an error,
and every skipped test has a stated reason. See "What BTL-clean means" in
[README.md](README.md). This is not BTL certification.

**Measured coverage:** 34 of the 43 selected tests ran, and all 34 passed.
- 4 of the 9 skipped tests need an operator, and the run was unattended.
- 5 do not apply to this device: it cannot create or delete objects, its only
  renameable or renumberable object is the Device (changed by restarting it),
  and it has no writable Present_Value.
- No test is skipped for a test-tool limitation.

Every BIBB the example claims had tests that ran: reading properties (including
the 7.1.1 Read Support procedure, against the EPICS), Who-Is / I-Am and
Who-Has / I-Have. The result is the same, test for test, as the C++ reference
port's and the C#, Go and Node.js ports'.

This run repeats the 2026-10-26 run on a newer VeriBACnet build (test selection,
EPICS writer and test scripts updated): the same 43 tests, every test with the
same result, and a regenerated EPICS identical to the committed one. The
2026-10-26 run itself replaced the 2026-10-23 run (43 tests, 34 PASS · 0 FAIL · 9 SKIP, 34
of 43 ran). Every test has the same result. What changed:
- The example moved to a newer CAS BACnet Stack (6.x @ 69b6249f). No source
  change was needed: the stack's regenerated Python bindings serve the example
  unchanged, the native library builds the same way, and the example's own Wire
  Tests pass. On the wire, Number_Of_APDU_Retries now reads 3 (the stack's new
  default, the value the standard suggests), and the IP Network Port no longer
  has Reference_Port (it has no reference port).
- The EPICS (`b-ss-python.tpi`) was regenerated from the device at the new
  stack.
- The project now states that the device has Octet String property values (the
  Network Port's addresses). That selects no extra test.

## Tests that did not pass

| Test | Result | Why |
|---|---|---|
| 7.3.2.10.9 Ensure Device Object_Name is Configurable | SKIP | Needs an operator to restart the device with another name (`--deviceName`); the run was unattended. |
| 7.3.2.10.10 Ensure Device Object_Identifier is Configurable | SKIP | Needs an operator to restart the device with another instance (`--deviceID`); the run was unattended. |
| 9.32.1.12 Who-Has After Object_Name Changed | SKIP | Needs an operator to change the Device's name, which this device does by a restart; the run was unattended. |
| 9.32.1.13 Who-Has After Object_Identifier Changed | SKIP | The Object_Identifier form of 9.32.1.12 (`--deviceID`), with the same reason. |
| 7.3.2.10.3 Database_Revision after creating an object | SKIP | The device cannot create objects, so the test does not apply. |
| 7.3.2.10.4 Database_Revision after deleting an object | SKIP | The device cannot delete objects by any means, so the test does not apply. |
| 7.3.2.10.5 Database_Revision after changing an Object_Name | SKIP | The only changeable Object_Name is the Device's, changed by restarting the device with a new configuration. The test plan skips the test in that case. |
| 7.3.2.10.6 Database_Revision after changing an Object_Identifier | SKIP | The only changeable Object_Identifier is the Device's. The test plan skips the test in that case. |
| 7.3.1.15 Number_Of_States Range Test | SKIP | Needs a writable multi-state Present_Value, and this device has none. |

No public issue has been opened for any of these.
