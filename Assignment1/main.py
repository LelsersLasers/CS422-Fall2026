#!/usr/bin/env python3

from pathlib import Path

from ping_test import run_ping_test
from locate_geo import run_locate_geo
from traceroute_test import run_traceroute_test
from plot_results import run_plot_results


ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "data" / "listed_iperf3_servers.json"


def main():
    print("\nRunning ping tests...")
    print("=" * 80)
    ping_output = run_ping_test(DATA_JSON)

    print("\nRunning geo location...")
    print("=" * 80)
    geo_output = run_locate_geo(ping_output)

    print("\nRunning traceroute tests...")
    print("=" * 80)
    trace_output = run_traceroute_test(DATA_JSON)

    print("\nGenerating plots...")
    print("=" * 80)
    run_plot_results(ping_output, geo_output, trace_output)

    print("\nDone.")


if __name__ == "__main__":
    main()
