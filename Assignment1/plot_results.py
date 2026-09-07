#!/usr/bin/env python3

import json
import math
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt


def load(path: Path):
    return json.loads(path.read_text())


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def get_own_location():
    data = subprocess.check_output(
        ["python", "-c",
         "import requests; print(requests.get('https://ipwho.is/', timeout=10).text)"],
        text=True,
    )
    obj = json.loads(data)
    return obj["latitude"], obj["longitude"]


def run_plot_results(
    ping_path: Path = Path("output/ping.json"),
    geo_path: Path = Path("output/geo.json"),
    trace_path: Path = Path("output/traceroute.json"),
    output_dir: Path = Path("output"),
) -> Path:
    """Generate all plots from ping, geo, and traceroute results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ping = load(ping_path)
    geo = {x["target"]: x for x in load(geo_path) if "latitude" in x}
    trace = load(trace_path)

    # 1(b): distance vs average RTT
    try:
        own_lat, own_lon = get_own_location()
    except Exception:
        own_lat = own_lon = None

    if own_lat is not None:
        points = []
        for row in ping:
            g = geo.get(row["target"])
            if g and row["responsive"] and row["avg_ms"] is not None:
                distance = haversine_km(
                    own_lat, own_lon, g["latitude"], g["longitude"]
                )
                points.append((distance, row["avg_ms"], row["target"]))

        if points:
            plt.figure()
            plt.scatter([p[0] for p in points], [p[1] for p in points])
            for x, y, label in points:
                plt.annotate(label, (x, y), fontsize=7)
            plt.xlabel("Geographical distance (km)")
            plt.ylabel("Average RTT (ms)")
            plt.title("Geographical distance vs. average RTT")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_dir / "distance_vs_rtt.pdf")
            plt.close()

    # 2(b): stacked latency breakdown. Each hop is plotted as the
    # incremental RTT from the previous responding hop.
    successful = [x for x in trace if x["hops"]]
    if successful:
        labels = [x["target"] for x in successful]

        # Collect the actual hop numbers that appeared in any traceroute.
        all_hop_numbers = sorted({
            hop["hop"]
            for result in successful
            for hop in result["hops"]
        })

        # Convert each traceroute into:
        # {hop_number: rtt_ms}
        hop_maps = [
            {
                hop["hop"]: hop["rtt_ms"]
                for hop in result["hops"]
            }
            for result in successful
        ]

        bottoms = [0.0] * len(successful)
        previous_rtts = [0.0] * len(successful)

        plt.figure()

        for hop_number in all_hop_numbers:
            values = []

            for idx, hop_map in enumerate(hop_maps):
                if hop_number in hop_map:
                    current_rtt = hop_map[hop_number]

                    # Approximate incremental RTT from the previous responding hop.
                    increment = current_rtt - previous_rtts[idx]

                    # Keep the stacked bar non-negative?
                    # traceroute RTTs are independent measurements,
                    # so decreases can occur naturally.
                    increment = max(0.0, increment)

                    values.append(increment)
                    previous_rtts[idx] = current_rtt
                else:
                    values.append(0.0)

            plt.bar(
                labels,
                values,
                bottom=bottoms,
                label=f"Hop {hop_number}"
            )

            bottoms = [
                bottom + value
                for bottom, value in zip(bottoms, values)
            ]

        plt.ylabel("Cumulative RTT (ms)")
        plt.xlabel("Destination IP")
        plt.title("Traceroute latency breakdown")
        plt.xticks(rotation=45, ha="right")
        plt.legend(fontsize=7, ncol=3)
        plt.tight_layout()
        plt.savefig(output_dir / "traceroute_breakdown.pdf")
        plt.close()

        # 2(c): hop count vs destination RTT
        hop_counts = [x["hops"][-1]["hop"] for x in successful]
        rtts = [x["hops"][-1]["rtt_ms"] for x in successful]

        plt.figure()
        plt.scatter(hop_counts, rtts)
        for x, y, label in zip(hop_counts, rtts, labels):
            plt.annotate(label, (x, y), fontsize=7)
        plt.xlabel("Hop count")
        plt.ylabel("Destination RTT (ms)")
        plt.title("Hop count vs. destination RTT")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "hop_count_vs_rtt.pdf")
        plt.close()

    print(f"Plots written to {output_dir}")
    return output_dir


if __name__ == "__main__":
    run_plot_results()
