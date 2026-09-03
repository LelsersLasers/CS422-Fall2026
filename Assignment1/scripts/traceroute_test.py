#!/usr/bin/env python3

import argparse
import json
import platform
import random
import re
import subprocess
from pathlib import Path


def read_targets(path: Path) -> list[str]:
    return [item["IP/HOST"] for item in json.loads(path.read_text())]


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
        # Typical Linux output:
        #  1  192.168.1.1  1.123 ms
        match = re.match(r"^\s*(\d+)\s+(\S+)\s+([\d.]+)\s+ms", line)
        if match:
            print(f"\tHop {match.group(1)}: {match.group(2)} ({match.group(3)} ms)")
            hops.append({
                "hop": int(match.group(1)),
                "address": match.group(2),
                "rtt_ms": float(match.group(3)),
            })

    destination_responded = bool(hops and hops[-1]["address"] == target)

    return {
        "target": target,
        "responsive": destination_responded,
        "hops": hops,
        "raw_return_code": proc.returncode,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/traceroute.json"))
    parser.add_argument("--max-hops", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=2)
    args = parser.parse_args()

    all_targets = read_targets(args.targets)
    if len(all_targets) > 20:
        selected_targets = random.sample(all_targets, 20)
    else:
        selected_targets = all_targets
    selected_targets = all_targets

    results = [
        traceroute(t, args.max_hops, args.timeout)
        for t in selected_targets
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
