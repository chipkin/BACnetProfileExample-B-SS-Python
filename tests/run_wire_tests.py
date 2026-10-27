#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.
"""Run every B-SS Wire Test, one after another, and report one result.

    python3 tests/run_wire_tests.py [--exe main.py] [--port 47824]

Exit code 0 = every check in every script passed.
"""
import argparse
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPOSITORY = TESTS.parent
sys.path.insert(0, str(REPOSITORY))

import wiretest  # noqa: E402  (the vendored harness at the repository root)

sys.path.insert(0, str(TESTS))
import bss_setup  # noqa: E402  (this example's launch command)

SCRIPTS = ["discovery_test.py", "configuration_test.py", "sensing_test.py", "failure_modes_test.py"]


def main():
    arguments = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arguments.add_argument("--exe", default=bss_setup.default_command(),
                           help="the example's main.py (run with this Python), or a command line that "
                                "starts it (default: main.py)")
    arguments.add_argument("--port", type=int, default=47824, help="the smart sensor's UDP port (default 47824)")
    args = arguments.parse_args()

    outcomes = []
    for script in SCRIPTS:
        print(f"\n===== {script} =====", flush=True)
        run = subprocess.run([sys.executable, "-B", str(TESTS / script), "--exe", args.exe, "--port", str(args.port)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(run.stdout, end="", flush=True)
        totals = [line for line in run.stdout.splitlines() if "checks passed" in line]
        outcomes.append((script, run.returncode, totals[-1] if totals else "no summary"))

    print("\n===== summary =====")
    for script, returncode, totals in outcomes:
        print(f"{'PASS' if returncode == 0 else 'FAIL'}  {script:24} {totals}")
    failed = [script for script, returncode, _ in outcomes if returncode != 0]
    print("ALL WIRE TESTS PASSED" if not failed else f"FAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
