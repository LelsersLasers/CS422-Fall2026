# CS 422 Assignment 2 

## Requirements

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run:

### With default parameters

```bash
python main.py
```
### With custom parameters

```text
python main.py -h

usage: main.py [-h] [-n DESTINATIONS] [-d DURATION] [-i INTERVAL]
               [--timeout TIMEOUT] [--max-attempts MAX_ATTEMPTS]
               [--block-size BLOCK_SIZE] [--algorithm ALGORITHM]
               [--seed SEED] [--servers SERVERS] [--output OUTPUT]

Run the Assignment 2 iPerf3 experiment (Parts 1-3) and produce plots.

options:
  -h, --help            show this help message and exit
  -n, --destinations DESTINATIONS
                        Number of successful destinations to reach (default:
                        10)
  -d, --duration DURATION
                        Per-test duration in seconds (default: 60)
  -i, --interval INTERVAL
                        TCP stats sampling interval in seconds (default:
                        1.0)
  --timeout TIMEOUT     Connection/read timeout in seconds (default: 15)
  --max-attempts MAX_ATTEMPTS
                        Maximum total test attempts per part (default: 30)
  --block-size BLOCK_SIZE
                        Data send block size in bytes, 1..1048576 (default:
                        131072)
  --algorithm ALGORITHM
                        Force a TCP congestion algorithm for Part 1
                        (default: OS default, e.g. CUBIC)
  --seed SEED           Random seed for reproducible server selection
  --servers SERVERS     Path to the JSON server list (default:
                        data/listed_iperf3_servers.json)
  --output OUTPUT       Output directory for data and plots (default:
                        output/)
```

## Results

Resulting plots are saved to `output/`

## Layout

```
main.py            Thin orchestrator: runs Parts 1–3, then renders all plots
plot_results.py    Unified plotter (goodput.pdf, tcp_stats.pdf, comparison.pdf)
part1/             Part 1 — iPerf3 socket program + goodput measurement
    protocol.py        iPerf3 wire protocol (cookie, states, length-prefixed JSON)
    tcp_stats.py       Linux TCP_INFO via getsockopt + per-interval sampling
    run_test.py        Single test (control + data sockets, select() send loop)
    run_iperf.py       Destination selection, test loop, summary/manifest output
    utils.py           Linux check, server-list loading, CSV/JSON writers
part2/             Part 2 — TCP stats tracing (post-processing of Part 1 output)
    run_tcp_stats.py   Picks the representative destination, emits its trace
part3/             Part 3 — CUBIC / Reno / BBR comparison
    run_algorithms.py  Selection pass + same-destination sweep passes
data/
    listed_iperf3_servers.json
output/            ALL intermediate data (CSV/JSON) and final graph PDFs
```

## Docker

I got no idea about this but we can figure this out once the implementation kind of works:

```bash
docker build -t cs422-assignment2 .
docker run --rm --network host -v "$PWD/data:/app/data:ro" -v "$PWD/output:/app/output" cs422-assignment2 -n 10 -d 60 -i 0.2
```