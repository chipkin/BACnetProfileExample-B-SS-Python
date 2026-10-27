#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-SS Wire Test: the sensor's Failure Modes - a broken sensor, and requests it cannot serve.

    python3 tests/failure_modes_test.py [--exe main.py] [--port 47824]

1. A broken sensor wire. ANSI/ASHRAE 135-2024 12.2.9: Reliability "provides an
   indication of whether the Present_Value or the operation of the physical input in
   question is "reliable" as far as the BACnet device or operator can determine";
   12.2.7: the FAULT flag of Status_Flags is "Logical TRUE (1) if the Reliability
   property is present and does not have a value of NO_FAULT_DETECTED". The test
   breaks the Simulation's sensor wire through its test-only hook (it creates the
   file named by CAS_EXAMPLE_TEST_SENSOR_FAULT_FILE) and a client reading the sensor
   must see Reliability OPEN_LOOP, Status_Flags FAULT, and a reading that no longer
   moves; once the file is deleted, NO_FAULT_DETECTED, no FAULT, a moving reading.

2. Requests a smart sensor must refuse, each with the answer the standard names:
   15.5.1.3.1 (ReadProperty) - "Specified object does not exist." OBJECT /
   UNKNOWN_OBJECT; "Specified property does not exist." PROPERTY / UNKNOWN_PROPERTY;
   "An array index is provided that is greater than the current length of the array."
   PROPERTY / INVALID_ARRAY_INDEX. 18.9 - a B-SS does not offer WriteProperty, so a
   WriteProperty is a Reject UNRECOGNIZED_SERVICE ("the Service Choice field specifies
   an unknown or unsupported service").
"""
import sys
import time

import bss_setup as setup
from bss_setup import ANALOG_INPUT, BINARY_INPUT, MULTI_STATE_INPUT
import wiretest
from wiretest import PROPERTY_PRESENT_VALUE, record, wait_until

# The Simulation checks the wire once a second; allow that, plus the round trip.
FAULT_NOTICED_SECONDS = 3.0
FROZEN_WATCH_SECONDS = 2.5   # longer than two Simulation steps


def readings_over(sensor, seconds):
    """Every distinct Present_Value of Analog Input 1 read over `seconds`, in order (read every
    0.25 s, so a reading that rises and falls back past a turning point still shows moving)."""
    readings = []
    finished = time.monotonic() + seconds
    while True:
        reading = sensor.value(ANALOG_INPUT, PROPERTY_PRESENT_VALUE)
        if not readings or readings[-1] != reading:
            readings.append(reading)
        if time.monotonic() >= finished:
            return readings
        time.sleep(0.25)


def health(sensor):
    return sensor.value(ANALOG_INPUT, setup.PROPERTY_RELIABILITY), sensor.value(ANALOG_INPUT, setup.PROPERTY_STATUS_FLAGS)


def refusals(sensor):
    answer = sensor.read((wiretest.OBJECT_TYPE_ANALOG_INPUT, 99), PROPERTY_PRESENT_VALUE)
    record("ReadProperty of Analog Input 99 (no such object) -> Error OBJECT / UNKNOWN_OBJECT",
           answer.error == (setup.ERROR_CLASS_OBJECT, setup.ERROR_CODE_UNKNOWN_OBJECT), answer.describe())
    answer = sensor.read(ANALOG_INPUT, setup.PROPERTY_HIGH_LIMIT)
    record("ReadProperty of Analog Input 1 High_Limit (no such property) -> Error PROPERTY / UNKNOWN_PROPERTY",
           answer.error == (setup.ERROR_CLASS_PROPERTY, setup.ERROR_CODE_UNKNOWN_PROPERTY), answer.describe())
    answer = sensor.read(MULTI_STATE_INPUT, setup.PROPERTY_STATE_TEXT, setup.NUMBER_OF_STATES + 1)
    record("ReadProperty of State_Text[4] (it has 3) -> Error PROPERTY / INVALID_ARRAY_INDEX",
           answer.error == (setup.ERROR_CLASS_PROPERTY, setup.ERROR_CODE_INVALID_ARRAY_INDEX), answer.describe())
    before = sensor.value(ANALOG_INPUT, PROPERTY_PRESENT_VALUE)
    answer = sensor.write(ANALOG_INPUT, PROPERTY_PRESENT_VALUE, wiretest.application_real(99.0))
    record("WriteProperty of Analog Input 1 Present_Value -> Reject UNRECOGNIZED_SERVICE (a B-SS is read-only)",
           answer.reject_reason == wiretest.REJECT_REASON_UNRECOGNIZED_SERVICE, answer.describe())
    after = sensor.value(ANALOG_INPUT, PROPERTY_PRESENT_VALUE)
    record("... and the reading is not 99.0 afterwards", after != 99.0, f"read {before} then {after}")


def main():
    args = setup.parser(__doc__).parse_args()
    fault_file = setup.fault_file_path(args.port)
    setup.remove(fault_file)
    example = setup.start_sensor(args, fault_file)
    sensor = setup.Sensor(args)
    try:
        record("Control: a healthy sensor - Reliability NO_FAULT_DETECTED, Status_Flags all FALSE",
               health(sensor) == (setup.NO_FAULT_DETECTED, setup.STATUS_FLAGS_NORMAL), f"read {health(sensor)}")
        readings = readings_over(sensor, FROZEN_WATCH_SECONDS)
        record("Control: the healthy reading moves", len(readings) > 1, f"read {readings}")

        fault_file.touch()
        broken_at = time.monotonic()
        noticed = wait_until(lambda: sensor.value(ANALOG_INPUT, setup.PROPERTY_RELIABILITY) == setup.OPEN_LOOP,
                             FAULT_NOTICED_SECONDS)
        record(f"Wire broken: Reliability reads OPEN_LOOP within {FAULT_NOTICED_SECONDS:.0f} s",
               noticed, f"read {health(sensor)[0]} after {time.monotonic() - broken_at:.1f} s")
        record("Wire broken: Status_Flags FAULT is TRUE (IN_ALARM, OVERRIDDEN, OUT_OF_SERVICE FALSE)",
               health(sensor)[1] == setup.STATUS_FLAGS_FAULT, f"read {health(sensor)[1]}")
        readings = readings_over(sensor, FROZEN_WATCH_SECONDS)
        record(f"Wire broken: the reading no longer moves (one value over {FROZEN_WATCH_SECONDS} s)",
               len(readings) == 1 and isinstance(readings[0], float), f"read {readings}")
        record("Wire broken: the other objects still answer (only Analog Input 1 is faulted)",
               sensor.value(BINARY_INPUT, PROPERTY_PRESENT_VALUE) in (0, 1)
               and sensor.value(BINARY_INPUT, setup.PROPERTY_STATUS_FLAGS) == setup.STATUS_FLAGS_NORMAL)
        refusals(sensor)

        setup.remove(fault_file)
        repaired = wait_until(lambda: sensor.value(ANALOG_INPUT, setup.PROPERTY_RELIABILITY) == setup.NO_FAULT_DETECTED,
                              FAULT_NOTICED_SECONDS)
        record(f"Wire repaired: Reliability back to NO_FAULT_DETECTED within {FAULT_NOTICED_SECONDS:.0f} s",
               repaired, f"read {health(sensor)[0]}")
        record("Wire repaired: Status_Flags all FALSE again", health(sensor)[1] == setup.STATUS_FLAGS_NORMAL,
               f"read {health(sensor)[1]}")
        readings = readings_over(sensor, FROZEN_WATCH_SECONDS)
        record("Wire repaired: the reading moves again", len(readings) > 1, f"read {readings}")
    finally:
        setup.remove(fault_file)
        sensor.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
