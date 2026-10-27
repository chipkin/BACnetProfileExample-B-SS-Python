# TODO

Open items and known limits at 1.2.0. Nothing here stops the example from
building, running or answering a client as [README.md](README.md) describes. Where
a line has a `ref:` tag, quote it when you contact Chipkin support.

## Known gaps

- **The stack library is a separate build, and the Linux and release workflows are not
  verified.** The stack's CMake presets build the library (see the README). This was
  checked on Windows only: the Linux build and the GitHub release workflow
  (`.github/workflows/release.yml`) have not been run since they were changed to use
  the presets. (ref: chipkin/chipkin-bacnet-testing-tool#455)
- **`common/` sends a frame the stack marks as a broadcast to the one address the stack
  gave, as a unicast.** The shared `common/` helper (the same design is in every
  example of the series) does this, so a router or gateway's reply that cl. 6.4.2
  requires to be a broadcast goes only to the requester. No effect on this sensor has
  been observed. Fix: change `common/`, then copy it into every example.
  (ref: chipkin/chipkin-bacnet-testing-tool#698)
- **The device hears its own broadcasts.** The operating system delivers a datagram
  sent to the subnet broadcast address back to the sending socket, so the start-up
  I-Am (and any Who-Is answer) is received by the device itself. It is harmless on a
  sensor. The stack does not yet treat these as its own transmissions, which on a
  router becomes a broadcast storm. (ref: chipkin/cas-bacnet-stack#4604)

## Not implemented, on purpose

- **No WriteProperty, no COV, no alarming, no scheduling, no trending.** A B-SS Smart
  Sensor is read-only (ANSI/ASHRAE 135-2024 Annex L.4.5), and a WriteProperty gets a
  Reject `unrecognized-service`.
- **The Device's `Object_Name` and instance are set at start-up** (`--deviceName`,
  `--deviceID`), not over the network, and are not kept across a restart. Start the
  example with the same options each time.
- **The sensor readings are simulated.** Replace the Simulation in `main.py`
  with your own sampling to use real hardware (TUTORIAL.md explains how).
- **No `--xml` option** (the C++ example has one).

## VeriBACnet

- A VeriBACnet run of this project (43 BTL tests) is 34 PASS, 0 FAIL, 9 SKIP; see
  `tests/veribacnet/RESULTS.md`. Four of the skips need an operator to restart the
  device with another name or instance, and five do not apply to a device that cannot
  create or delete objects.
