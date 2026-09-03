#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_JSON = Path(ROOT, "data", "listed_iperf3_servers.json")


def run(cmd):
    print(" $ ", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    python = sys.executable

    run([python, "scripts/ping_test.py", str(DATA_JSON)])
    run([python, "scripts/locate_geo.py", "output/ping.json"])
    run([python, "scripts/traceroute_test.py", str(DATA_JSON)])
    run([python, "scripts/plot_results.py"])

    print("\nDone.")


if __name__ == "__main__":
    main()
