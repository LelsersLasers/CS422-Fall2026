#!/usr/bin/env python3
"""Geolocate responsive IPs using ipwho.is and write JSON."""

import argparse
import json
import time
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ping_json", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/geo.json"))
    args = parser.parse_args()

    ping_results = json.loads(args.ping_json.read_text())
    results = []

    for row in ping_results:
        ip = row["target"]
        if not row["responsive"] or ip == "self":
            continue

        print(f"Geolocating {ip}...")

        try:
            response = requests.get(f"https://ipwho.is/{ip}", timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("success", False):
                print(f"\tLocated {ip}: {data.get('city')}, {data.get('country')}")

                results.append({
                    "target": ip,
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "country": data.get("country"),
                    "city": data.get("city"),
                })
            else:
                results.append({"target": ip, "error": data.get("message", "unknown error")})
        except requests.RequestException as exc:
            results.append({"target": ip, "error": str(exc)})

        time.sleep(0.2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
