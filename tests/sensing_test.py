#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-SS Wire Test: a client reading the sensor gets what it measures now (DS-RP-B).

    python3 tests/sensing_test.py [--exe main.py] [--port 47821]

ANSI/ASHRAE 135-2024 Annex L.4.5, the B-SS Profile Function: "Ability to provide
values for any of its BACnet objects upon request". A sensor that answers with the
same number forever answers every ReadProperty and still provides no value, so this
test reads each sensor object again and again over ten seconds and checks that what
it reads follows the sensor Simulation (main.py section 2):

    Analog Input 1 "Bronze"        0.5 C a second, between 18.0 and 26.0
    Binary Input 1 "Emerald"       toggles every 3 s
    Multi-State Input 1 "Hot Pink" steps 1 -> 2 -> 3 -> 1 every 4 s

The Peer is a Python BACnet client on 127.0.0.1 - what a controller polling the
sensor does on a real site.
"""
import math
import sys
import time

import bss_setup as setup
from bss_setup import ANALOG_INPUT, BINARY_INPUT, MULTI_STATE_INPUT
import wiretest
from wiretest import PROPERTY_PRESENT_VALUE, record

OBSERVE_SECONDS = 12.0
SAMPLE_SECONDS = 0.5


def observe(sensor):
    """[(AI asked at, AI, BI, MSI, AI answered at)] every SAMPLE_SECONDS for OBSERVE_SECONDS; the
    times are seconds since the first read. Both ends of the Analog Input read are kept so a
    read that needed a retry cannot make two readings look closer together than they were."""
    samples = []
    started = time.monotonic()
    while time.monotonic() - started < OBSERVE_SECONDS:
        asked_at = time.monotonic() - started
        analog = sensor.value(ANALOG_INPUT, PROPERTY_PRESENT_VALUE)
        answered_at = time.monotonic() - started
        samples.append((asked_at, analog, sensor.value(BINARY_INPUT, PROPERTY_PRESENT_VALUE),
                        sensor.value(MULTI_STATE_INPUT, PROPERTY_PRESENT_VALUE), answered_at))
        time.sleep(max(0.0, started + len(samples) * SAMPLE_SECONDS - time.monotonic()))
    return samples


def step_count_fits(change, seconds_apart):
    """True when `change` is a whole number of Simulation steps and no more steps than the
    Simulation's once-a-second tick can make in `seconds_apart`."""
    steps = change / setup.ANALOG_INPUT_STEP
    return steps == int(steps) and steps <= math.floor(seconds_apart) + 1


def changes(values):
    """The values with consecutive repeats collapsed: [1, 1, 2, 2, 3] -> [1, 2, 3]."""
    collapsed = []
    for value in values:
        if not collapsed or collapsed[-1] != value:
            collapsed.append(value)
    return collapsed


def main():
    args = setup.parser(__doc__).parse_args()
    example = setup.start_sensor(args)
    sensor = setup.Sensor(args)
    try:
        record("Control: Analog Input 1 answers in degrees Celsius",
               sensor.value(ANALOG_INPUT, setup.PROPERTY_UNITS) == setup.DEGREES_CELSIUS)
        record("Control: State_Text names the three states On / Off / Auto",
               [sensor.value(MULTI_STATE_INPUT, setup.PROPERTY_STATE_TEXT, index) for index in (1, 2, 3)]
               == ["On", "Off", "Auto"])

        samples = observe(sensor)
        analog = [sample[1] for sample in samples]
        binary = [sample[2] for sample in samples]
        multi_state = [sample[3] for sample in samples]
        record(f"Every one of the {len(samples) * 3} reads over {OBSERVE_SECONDS:.0f} s answered with a value",
               all(isinstance(value, (int, float)) for sample in samples for value in sample[1:4]),
               f"{[sample for sample in samples if not all(isinstance(value, (int, float)) for value in sample[1:4])]}")
        if not all(isinstance(value, (int, float)) for sample in samples for value in sample[1:4]):
            return wiretest.summary()

        # Analog Input 1: it moves, by the Simulation's 0.5 C steps, inside its range.
        analog_steps = changes(analog)
        record("Analog Input 1 changes between reads (the reading is live, not a constant)",
               len(analog_steps) >= 5, f"read {analog_steps}")
        too_fast = [(round(later[0], 1), earlier[1], later[1]) for earlier, later in zip(samples, samples[1:])
                    if not step_count_fits(abs(later[1] - earlier[1]), later[4] - earlier[0])]
        record("... in whole 0.5 C steps, no more than one step per second between two reads",
               not too_fast, f"(at s, from, to) {too_fast}")
        record(f"... at the Simulation's rate: at least {setup.ANALOG_INPUT_STEP * 7:.1f} C of movement in "
               f"{OBSERVE_SECONDS:.0f} s",
               sum(abs(later - earlier) for earlier, later in zip(analog_steps, analog_steps[1:]))
               >= setup.ANALOG_INPUT_STEP * 7, f"read {analog_steps}")
        record(f"... and inside {setup.ANALOG_INPUT_LOWEST} .. {setup.ANALOG_INPUT_HIGHEST} C",
               all(setup.ANALOG_INPUT_LOWEST <= value <= setup.ANALOG_INPUT_HIGHEST for value in analog),
               f"read {analog_steps}")

        # Binary Input 1: it toggles, and holds each state for about 3 s.
        binary_steps = changes(binary)
        record(f"Binary Input 1 toggles active / inactive (at least 3 changes in {OBSERVE_SECONDS:.0f} s)",
               len(binary_steps) >= 4 and set(binary_steps) == {0, 1}, f"read {binary_steps}")
        toggled_at = [samples[index][0] for index in range(1, len(samples)) if binary[index] != binary[index - 1]]
        held_seconds = [round(later - earlier, 1) for earlier, later in zip(toggled_at, toggled_at[1:])]
        record(f"... holding each state for about {setup.BINARY_INPUT_TOGGLE_SECONDS} s",
               held_seconds and all(abs(held - setup.BINARY_INPUT_TOGGLE_SECONDS) <= 1.0 for held in held_seconds),
               f"held {held_seconds} s")

        # Multi-State Input 1: it steps through its states in order.
        multi_state_steps = changes(multi_state)
        record("Multi-State Input 1 steps to a new state at least twice",
               len(multi_state_steps) >= 3, f"read {multi_state_steps}")
        # Judge only reads less than one step period apart: a read delayed by retries could
        # otherwise have slept through a whole state.
        out_of_order = [(round(later[0], 1), earlier[3], later[3]) for earlier, later in zip(samples, samples[1:])
                        if later[3] != earlier[3] and later[3] != earlier[3] % setup.NUMBER_OF_STATES + 1
                        and later[0] - earlier[0] < setup.MULTI_STATE_INPUT_STEP_SECONDS]
        record("... each step to the next state (1 -> 2 -> 3 -> 1), never out of 1..Number_Of_States",
               not out_of_order and all(1 <= value <= setup.NUMBER_OF_STATES for value in multi_state),
               f"read {multi_state_steps}; out of order (at s, from, to) {out_of_order}")
    finally:
        sensor.close()
        example.stop()
        if not all(wiretest.results.RESULTS):
            example.keep_log()
    return wiretest.summary()


if __name__ == "__main__":
    sys.exit(main())
