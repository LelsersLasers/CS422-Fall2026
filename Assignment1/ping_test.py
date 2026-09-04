#!/usr/bin/env python3

import json
import platform
import re
import subprocess
from pathlib import Path

from utils import get_local_ip, read_targets


def ping(target: str, count: int = 5, timeout: int = 2) -> dict:
    print(f"Pinging {target}...")

    system = platform.system().lower()

    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), target]
    else:
        cmd = ["ping", "-i", "0.1", "-c", str(count), "-W", str(timeout), target]

    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=count * (timeout + 2) + 5)
    output = proc.stdout + proc.stderr

    # Linux/macOS ping summary usually looks like:
    # round-trip min/avg/max/stddev = 10.1/12.3/14.5/1.2 ms
    match = re.search(
        r"(?:min/avg/max(?:/mdev|/stddev)?\s*=\s*)"
        r"([\d.]+)/([\d.]+)/([\d.]+)",
        output,
    )

    if not match:
        print(f"\tNo summary found for {target}. Output:\n{output}")
        return {
            "target": target,
            "responsive": False,
            "min_ms": None,
            "avg_ms": None,
            "max_ms": None,
        }

    print(f"\tResults for {target}: {match.group(1)}/{match.group(2)}/{match.group(3)}")
    return {
        "target": target,
        "responsive": True,
        "min_ms": float(match.group(1)),
        "avg_ms": float(match.group(2)),
        "max_ms": float(match.group(3)),
    }


def run_ping_test(
    targets_path: Path,
    output_path: Path = Path("output/ping.json"),
    count: int = 5,
    timeout: int = 2,
) -> Path:
    """Run ping tests against all targets and write results to output_path."""
    all_ping_targets = read_targets(targets_path)
    all_ping_targets.append(get_local_ip())
    results = [ping(t, count, timeout) for t in all_ping_targets]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {output_path}")
    return output_path


if __name__ == "__main__":
    run_ping_test(Path("data/listed_iperf3_servers.json"))
