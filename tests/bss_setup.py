# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""What B-SS's Wire Tests share: this smart sensor's numbers, and starting it.

The setup, all on one host:

    test client (127.0.0.1, ephemeral UDP port) - the Peer: a Python BACnet client
        |  BACnet/IP, unicast
    BACnetExampleBSS   UDP --port   Analog Input 1 "Bronze", Binary Input 1 "Emerald",
                                    Multi-State Input 1 "Hot Pink"

The Peer plays the part of whatever reads a smart sensor on a real site - a
controller polling a room temperature, an operator workstation. It reads the sensor
over the wire exactly as those would; nothing reaches into the example any other
way, except the Simulation's one test-only hook: the file named by
CAS_EXAMPLE_TEST_SENSOR_FAULT_FILE, whose existence breaks the simulated sensor wire.
"""
import argparse
import os
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)

# Match main.py (the Python port of BACnetProfileExample-B-SS-CPP's main.cpp).
DEVICE_INSTANCE = 389001
ANALOG_INPUT = (wiretest.OBJECT_TYPE_ANALOG_INPUT, 1)             # "Bronze"
BINARY_INPUT = (wiretest.OBJECT_TYPE_BINARY_INPUT, 1)             # "Emerald"
MULTI_STATE_INPUT = (wiretest.OBJECT_TYPE_MULTI_STATE_INPUT, 1)   # "Hot Pink"

# The Simulation (main.py section 2): once a second the temperature moves 0.5 C
# between 18.0 and 26.0; the binary input toggles every 3 s; the multi-state input
# steps 1 -> 2 -> 3 -> 1 every 4 s.
ANALOG_INPUT_LOWEST, ANALOG_INPUT_HIGHEST, ANALOG_INPUT_STEP = 18.0, 26.0, 0.5
BINARY_INPUT_TOGGLE_SECONDS = 3
MULTI_STATE_INPUT_STEP_SECONDS = 4
NUMBER_OF_STATES = 3
SENSOR_FAULT_FILE_VARIABLE = "CAS_EXAMPLE_TEST_SENSOR_FAULT_FILE"

# Every request: 0.6 s for an answer, then up to 3 resends (Sensor below).
REQUEST_TIMEOUT = 0.6
RETRIES = 3

# Properties (cl. 12; numbers from cl. 21 BACnetPropertyIdentifier).
PROPERTY_HIGH_LIMIT = 45
PROPERTY_RELIABILITY = 103
PROPERTY_STATE_TEXT = 110
PROPERTY_STATUS_FLAGS = 111
PROPERTY_UNITS = 117
DEGREES_CELSIUS = 62

# BACnetReliability (cl. 21), BACnetStatusFlags bit order {IN_ALARM, FAULT, OVERRIDDEN,
# OUT_OF_SERVICE} (cl. 12.2.7), Error classes / codes and Reject reasons (cl. 18).
NO_FAULT_DETECTED, OPEN_LOOP = 0, 4
STATUS_FLAGS_NORMAL = [False, False, False, False]
STATUS_FLAGS_FAULT = [False, True, False, False]
ERROR_CLASS_OBJECT, ERROR_CLASS_PROPERTY = 1, 2
ERROR_CODE_UNKNOWN_OBJECT, ERROR_CODE_UNKNOWN_PROPERTY, ERROR_CODE_INVALID_ARRAY_INDEX = 31, 32, 42


def default_command():
    """This port's program: main.py at the repository root."""
    return str(REPOSITORY / "main.py")


def launch_command(exe):
    """`--exe` as a command line. A path to a .py file is run with this Python (sys.executable);
    any other existing path is used as it is; anything else is a command line whose first word
    is the program and the rest come before the example's own options (e.g.
    --exe "python3.10 main.py"). wiretest.start() takes one executable and its arguments, so
    this is the only place a launch command is split."""
    if Path(exe).exists():
        return [sys.executable, str(Path(exe).resolve())] if exe.endswith(".py") else [exe]
    words = shlex.split(exe, posix=os.name != "nt")
    words = [word[1:-1] if len(word) > 1 and word[0] == word[-1] == '"' else word for word in words]
    # A bare program name ("python3") is looked up on PATH: wiretest makes the first word an
    # absolute path, which would otherwise point into the current folder.
    return [shutil.which(words[0]) or words[0]] + words[1:]


def start(exe, arguments, label, environment=None):
    """wiretest.start() for a `--exe` that may be a command line (launch_command)."""
    command = launch_command(exe)
    return wiretest.start(command[0], command[1:] + list(arguments), label, environment)


def parser(description):
    arguments = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=default_command(),
                           help="the example's main.py (run with this Python), or a command line that "
                                "starts it (default: main.py)")
    arguments.add_argument("--port", type=int, default=47821,
                           help="the smart sensor's UDP port (default 47821)")
    return arguments


def fault_file_path(port):
    """Where this run's broken-wire file lives (one per port, so parallel runs do not share it)."""
    return Path(tempfile.gettempdir()) / f"bss-sensor-fault-{port}"


def start_sensor(args, fault_file=None):
    """Start the example; with `fault_file`, its broken-wire hook watches that path."""
    environment = {SENSOR_FAULT_FILE_VARIABLE: str(fault_file)} if fault_file else None
    return start(args.exe, ["--port", args.port], "sensor", environment)


class Sensor:
    """The smart sensor as the Peer sees it: a wiretest.Client aimed at its port, with a short
    timeout and visible retries (wiretest 0.7.0 Client(retries=, timeout=)): a request
    unanswered after REQUEST_TIMEOUT is sent again, up to RETRIES times, as a BACnet client
    does (Number_Of_APDU_Retries), each resend printing [RETRY]. A busy Windows host loses the
    odd UDP datagram even on loopback, where an answer takes milliseconds - so the timeout is
    short and a loss costs well under a second."""

    def __init__(self, args):
        self.client = wiretest.Client(retries=RETRIES, timeout=REQUEST_TIMEOUT)
        self.port = args.port

    def read(self, object_identifier, property_identifier, array_index=None):
        return self.client.read_property(self.port, *object_identifier, property_identifier, array_index)

    def value(self, object_identifier, property_identifier, array_index=None):
        """The decoded value, or 'no answer' / 'error' so a comparison fails readably."""
        answer = self.read(object_identifier, property_identifier, array_index)
        if not answer.answered:
            return "no answer"
        return answer.value if answer.ok else "error"

    def write(self, object_identifier, property_identifier, value_octets):
        return self.client.write_property(self.port, *object_identifier, property_identifier, value_octets)

    def close(self):
        self.client.close()


def remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
