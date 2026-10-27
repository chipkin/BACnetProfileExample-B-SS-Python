#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""B-SS Wire Test: the command line - the Device's identity is configurable at start-up
(--deviceID, --deviceName), and --help lists exactly the options the example reads.

    python3 tests/configuration_test.py [--exe main.py] [--port 47824]

BACnet requires a device's Object_Identifier and Object_Name to be configurable
(135-2024 cl. 12.1.1.3, 12.1.1.4; BTL tests 7.3.2.10.9 / 7.3.2.10.10): Object_Name must
be unique across the internetwork, so two units of one product cannot share a
compile-time name. This sensor takes both on its command line. The test starts it
four times, then asks it for --help:

    1. with no identity options     -> Device 389001 "Chipkin Example B-SS" (the defaults)
    2. --deviceID 389901 --deviceName "Chipkin Example B-SS Unit 2"
                                    -> Who-Is, ReadProperty and Who-Has all see the
                                       configured instance and name; 389001 is gone
    3. invalid names (empty, 256 bytes) -> a warning, and the default name; a
       255-byte name is accepted whole
    4. --help lists --port, --deviceID and --deviceName, and neither --dcc-password
       (a B-SS has no DeviceCommunicationControl) nor --xml (this port has no XML log)

Exit code 0 = every check passed.
"""
import subprocess
import sys

import bss_setup as setup
import wiretest
from wiretest import record as record_check, summary

DEFAULT_INSTANCE = setup.DEVICE_INSTANCE
DEFAULT_NAME = "Chipkin Example B-SS"
CONFIGURED_INSTANCE = 389901
CONFIGURED_NAME = "Chipkin Example B-SS Unit 2"
LONGEST_NAME = "N" * 255          # common/ MAX_DEVICE_NAME_LENGTH
TOO_LONG_NAME = "N" * 256
SERVICE_I_HAVE, SERVICE_WHO_HAS = 1, 7
PDU_UNCONFIRMED_REQUEST = 0x10


def who_has_by_name(name):
    """A Who-Has APDU naming the object by Object_Name (cl. 16.9.1: context tag 3)."""
    text = b"\x00" + name.encode("utf-8")          # character set 0 = UTF-8
    return bytes([PDU_UNCONFIRMED_REQUEST, SERVICE_WHO_HAS, 0x3D, len(text)]) + text


def is_i_have(apdu, device_instance, name):
    """An I-Have from `device_instance` naming the Device object `name` (cl. 16.8.1)."""
    device_identifier = ((wiretest.OBJECT_TYPE_DEVICE << 22) | device_instance).to_bytes(4, "big")
    name_octets = b"\x00" + name.encode("utf-8")
    return (len(apdu) > 2 and apdu[0] == PDU_UNCONFIRMED_REQUEST and apdu[1] == SERVICE_I_HAVE
            and apdu[2:7] == b"\xC4" + device_identifier and name_octets in apdu)


def record(text, ok, failure_detail):
    """record() with the detail shown only when the check fails."""
    record_check(text, ok, "" if ok else failure_detail)


def object_name(client, port, instance):
    answer = client.read_property(port, wiretest.OBJECT_TYPE_DEVICE, instance, wiretest.PROPERTY_OBJECT_NAME)
    if not answer.answered:
        return "no answer"
    return answer.value if answer.ok else answer.describe()


def main():
    args = setup.parser(__doc__).parse_args()
    client = wiretest.Client(retries=setup.RETRIES, timeout=setup.REQUEST_TIMEOUT)
    try:
        # 1. The defaults - the control: the configured run below must differ from this.
        sensor = setup.start(args.exe, ["--port", args.port], "sensor")
        try:
            record(f"no options: Device {DEFAULT_INSTANCE} answers Who-Is",
                   client.who_is(args.port, DEFAULT_INSTANCE) is not None, "no I-Am")
            name = object_name(client, args.port, DEFAULT_INSTANCE)
            record(f"no options: Object_Name is the default \"{DEFAULT_NAME}\"", name == DEFAULT_NAME, f"read {name!r}")
        finally:
            sensor.stop()

        # 2. Both configured.
        sensor = setup.start(args.exe, ["--port", args.port, "--deviceID", CONFIGURED_INSTANCE,
                                        "--deviceName", CONFIGURED_NAME], "sensor")
        try:
            record(f"--deviceID {CONFIGURED_INSTANCE}: the device answers Who-Is as {CONFIGURED_INSTANCE}",
                   client.who_is(args.port, CONFIGURED_INSTANCE) is not None, "no I-Am")
            name = object_name(client, args.port, CONFIGURED_INSTANCE)
            record(f"--deviceName: Object_Name reads \"{CONFIGURED_NAME}\"", name == CONFIGURED_NAME, f"read {name!r}")
            old = client.read_property(args.port, wiretest.OBJECT_TYPE_DEVICE, DEFAULT_INSTANCE,
                                       wiretest.PROPERTY_OBJECT_NAME)
            record(f"Device {DEFAULT_INSTANCE} no longer exists: Error OBJECT / UNKNOWN_OBJECT",
                   old.error == (setup.ERROR_CLASS_OBJECT, setup.ERROR_CODE_UNKNOWN_OBJECT), old.describe())
            record("the ready line names the configured device",
                   f"Device {CONFIGURED_INSTANCE} (\"{CONFIGURED_NAME}\") ready" in sensor.output(), "not in the console")
            found = None
            for attempt in range(1 + setup.RETRIES):
                if attempt:
                    print("[RETRY] Who-Has got no I-Have - sent again", flush=True)
                client.frames.clear()
                client.send(wiretest.bvlc(wiretest.npdu(who_has_by_name(CONFIGURED_NAME))), args.port)
                found = client.wait_for(lambda frame: is_i_have(frame.payload, CONFIGURED_INSTANCE, CONFIGURED_NAME),
                                        2.0)
                if found is not None:
                    break
            record(f"Who-Has \"{CONFIGURED_NAME}\" -> I-Have from Device {CONFIGURED_INSTANCE} with that name",
                   found is not None, "no I-Have")
        finally:
            sensor.stop()

        # 3. The boundaries: invalid names keep the default, the longest valid one is kept whole.
        for label, value, expected in (("an empty --deviceName", "", DEFAULT_NAME),
                                       ("a 256-byte --deviceName", TOO_LONG_NAME, DEFAULT_NAME),
                                       ("a 255-byte --deviceName", LONGEST_NAME, LONGEST_NAME)):
            sensor = setup.start(args.exe, ["--port", args.port, "--deviceName", value], "sensor")
            try:
                name = object_name(client, args.port, DEFAULT_INSTANCE)
                shown = name if len(str(name)) < 40 else f"{len(name)} bytes"
                record(f"{label}: Object_Name reads {'the default' if expected == DEFAULT_NAME else 'it whole'}",
                       name == expected, f"read {shown!r}")
                if expected == DEFAULT_NAME:
                    record(f"{label}: the console warns", "invalid --deviceName" in sensor.output(), "no warning")
            finally:
                sensor.stop()

        # 4. The help lists the options this example reads, and no other.
        shown = subprocess.run(setup.launch_command(args.exe) + ["--help"], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=20).stdout
        for option in ("--port", "--deviceID", "--deviceName"):
            record(f"--help lists {option}", option in shown, "not listed")
        for option, why in (("--dcc-password", "a B-SS has no DeviceCommunicationControl"),
                            ("--xml", "this port has no XML frame log")):
            record(f"--help does not list {option} ({why})", option not in shown, "listed")
    finally:
        client.close()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
