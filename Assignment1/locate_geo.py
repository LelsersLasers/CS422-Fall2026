#!/usr/bin/env python3

import json
import time
from pathlib import Path

import requests


def run_locate_geo(
    ping_json_path: Path,
    output_path: Path = Path("output/geo.json"),
) -> Path:
    """Geolocate each responsive target from ping results and write results to output_path."""
    ping_results = json.loads(ping_json_path.read_text())
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {output_path}")
    return output_path


if __name__ == "__main__":
    run_locate_geo(Path("output/ping.json"))
