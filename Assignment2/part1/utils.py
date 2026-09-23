#!/usr/bin/env python3
"""Shared utilities for iPerf3 throughput testing.

Handles server list parsing, platform validation, and data file output.
"""

import csv
import json
import platform
import random
from pathlib import Path


def expect_linux() -> None:
    """Verify the code is running on Linux.

    TCP_INFO and TCP_CONGESTION socket options are Linux-specific.

    Raises:
        RuntimeError: If the platform is not Linux.
    """
    if platform.system() != 'Linux':
        raise RuntimeError(
            f"This tool requires Linux for TCP_INFO/TCP_CONGESTION. "
            f"Current platform: {platform.system()}"
        )
    if not hasattr(__import__('socket'), 'TCP_CONGESTION'):
        raise RuntimeError("socket.TCP_CONGESTION not available on this system")


def load_servers(path: Path, rng: random.Random) -> list[dict]:
    """Parse the iperf3 server list JSON and return a FLATTENED, shuffled list.

    The server list format from iperf3serverlist.net contains entries like:
        {"IP/HOST": "1.2.3.4", "PORT": "5201-5210", "PROVIDER": "...", ...}

    Port ranges (e.g., "5201-5210") indicate alternative listener ports on
    the same server. We expand ranges into individual (host, port) pairs,
    deduplicate, and shuffle the entire flat list.

    This ensures the main test loop tries different hosts in round-robin
    fashion, rather than exhausting all ports on one failing host.

    Args:
        path: Path to the JSON server list file.
        rng: Random instance for reproducible shuffling (seeded by CLI --seed).

    Returns:
        List of dicts, each with keys: host, port, provider, country.
    """
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        raise ValueError("Server list must be a JSON array")

    candidates = []
    seen = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        host = str(entry.get('IP/HOST', '')).strip()
        raw_port = str(entry.get('PORT', '')).strip()

        if not host or not raw_port:
            continue

        try:
            if '-' in raw_port:
                # Port range: "5201-5210" -> [5201, 5202, ..., 5210]
                a, b = map(int, raw_port.split('-', 1))
                if not (1 <= a <= b <= 65535):
                    continue
                ports = list(range(a, b + 1))
                rng.shuffle(ports)  # Shuffle so we don't always try 5201 first.
            else:
                port = int(raw_port)
                if not (1 <= port <= 65535):
                    continue
                ports = [port]
        except ValueError:
            continue

        provider = str(entry.get('PROVIDER', ''))
        country = str(entry.get('COUNTRY', ''))

        for port in ports:
            if (host, port) not in seen:
                candidates.append({
                    'host': host,
                    'port': port,
                    'provider': provider,
                    'country': country,
                })
                seen.add((host, port))

    # Shuffle the entire flat list for random server selection.
    rng.shuffle(candidates)
    return candidates


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """Write a list of dicts to a CSV file.

    Args:
        path: Output file path.
        rows: List of row dicts.
        fields: Column names in order.
    """
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    """Write a Python object to a pretty-printed JSON file.

    Args:
        path: Output file path.
        obj: Serializable Python object.
    """
    path.write_text(json.dumps(obj, indent=2))
