#!/usr/bin/env python3

import argparse
import json
import platform
import re
import subprocess
from pathlib import Path


def read_targets(path: Path) -> list[str]:
    return [item["IP/HOST"] for item in json.loads(path.read_text())]


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/ping.json"))
    parser.add_argument("-c", "--count", type=int, default=5)
    parser.add_argument("-t", "--timeout", type=int, default=2)
    args = parser.parse_args()

    results = [ping(t, args.count, args.timeout) for t in read_targets(args.targets)]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
