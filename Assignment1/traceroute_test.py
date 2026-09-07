#!/usr/bin/env python3

import json
import platform
import random
import re
import subprocess
from pathlib import Path

from utils import read_targets


def traceroute(target: str, max_hops: int = 30, timeout: int = 2) -> dict:
    system = platform.system().lower()

    if system == "windows":
        cmd = ["tracert", "-d", "-h", str(max_hops), target]
    else:
        # -n: no DNS, -q 1: one probe/hop, -w: timeout seconds
        cmd = ["traceroute", "-n", "-q", "1", "-w", str(timeout), "-m", str(max_hops), target]

    print(f"Tracing route to {target}...")

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=max_hops * (timeout + 1) + 10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"target": target, "responsive": False, "error": str(exc), "hops": []}

    hops = []
    for line in proc.stdout.splitlines():
        # Filter out non-responsive hops (lines like "  2  * * *")
        if re.match(r"^\s*\d+\s+(\*\s+)+", line):
            print(f"\t{line.strip()} (filtered non-responsive)")
            continue
        # Typical Linux output:
        #  1  192.168.1.1  1.123 ms
        match = re.match(r"^\s*(\d+)\s+(\S+)\s+([\d.]+)\s+ms", line)
        if match:
            hops.append({
                "hop": int(match.group(1)),
                "address": match.group(2),
                "rtt_ms": float(match.group(3)),
            })
            print(f"\tHop {match.group(1)}: {match.group(2)} ({match.group(3)} ms)")

    destination_responded = bool(hops and hops[-1]["address"] == target)
    if not destination_responded:
        print(f"\tDestination {target} did not respond. Last hop: {hops[-1]['address'] if hops else 'None'}")

    return {
        "target": target,
        "responsive": destination_responded,
        "hops": hops,
        "raw_return_code": proc.returncode,
    }


def run_traceroute_test(
    targets_path: Path,
    output_path: Path = Path("output/traceroute.json"),
    count: int = 5,
    max_hops: int = 30,
    timeout: int = 2,
    seed: int | None = None,
) -> Path:
    """Run traceroute tests until exactly count successful traces are collected.

    Non-responsive targets are replaced by random picks from the remaining pool
    so the final result always contains count entries with hop data.
    """
    if seed is not None:
        random.seed(seed)

    all_targets = read_targets(targets_path)
    pool = list(all_targets)
    results: list[dict] = []

    while len(results) < count and pool:
        target = pool.pop(random.randrange(len(pool)))
        result = traceroute(target, max_hops, timeout)
        if result["hops"]:
            results.append(result)
        else:
            print(f"\tSkipping non-responsive target {target}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {output_path}")
    return output_path


if __name__ == "__main__":
    run_traceroute_test(Path("data/listed_iperf3_servers.json"))
