# CS 422 Assignment 2 — iPerf3, TCP Stats, Congestion Control

Native Python socket implementation of an iperf3 TCP sender. It does **not** invoke the iperf3 binary. Requires Linux (including WSL2), Python 3.10+, matplotlib, and a real public iperf3 server list at `data/listed_iperf3_servers.json`.

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

## Run

```bash
python3 -m pip install -r requirements.txt
python3 main.py -n 10 -d 60 -i 1.0
```

CLI options: `-n` destinations, `-d` per-test duration (s), `-i` sampling interval (s), `--timeout`, `--max-attempts`, `--block-size` (1..1048576), `--algorithm` (force an algorithm for Part 1; default OS default, e.g. CUBIC), `--seed`, `--servers`, `--output` (default `output/`).

For an initial smoke test use `-n 1 -d 3 -i 0.2 --max-attempts 5`. For reproducible selection use `--seed 42`. Ports expressed as `9205-9240` are alternative ports of one destination; each is tried until success or the global attempt limit. Hosts are randomly shuffled. The program sends one TCP stream in normal (not reverse/UDP) mode; the OPTIONS column is informational only.

### Parts

- **Part 1** — connects to iperf3 servers from the candidate list until `-n` destinations succeed, measuring per-interval acknowledged goodput with the OS default algorithm.
- **Part 2** — selects the representative destination (highest mean goodput from Part 1's `summary.csv`; the OS default algorithm is exactly what Part 1 measured) and emits its full TCP stats trace for visualization.
- **Part 3** — a CUBIC selection pass picks the destinations, then the SAME `(host, port)` pairs are re-tested with Reno and BBR. The algorithm actually used is queried back from the data socket and recorded in every sample row, so a kernel that lacks the requested algorithm is visible in the output.

## Outputs (all under `output/`)

Part 1: `{run_id}_samples.csv` (per-interval TCP stats + goodput), `{run_id}_server_results.json` (final iperf3 server result), `summary.csv` (per-run min/median/mean/p95 goodput), `failures.csv`, `manifest.json`, `goodput.pdf` (per-destination time series).

Part 2: `representative_samples.csv` + `representative.json` (selection metadata), `tcp_stats.pdf` (time series + scatter pages).

Part 3 (under `output/part3/`): `{cubic,reno,bbr}/{run_id}_samples.csv` + per-run server JSONs, `comparison_summary.csv` (one row per destination × algorithm), `manifest.json`, `comparison.pdf` (per-algorithm pages with consistent axis scales).

The goodput numerator is **delta of Linux tcpi_bytes_acked** on the **data** socket, not application bytes passed to `send()`. The initial baseline is taken after TEST_RUNNING, so TCP handshake/cookie acknowledgments are excluded from the measured intervals. The final partial interval is retained. Samples are taken in the sender's event loop and therefore may be delayed under scheduling load; actual elapsed time is used in the denominator. TCP_INFO uses Linux native-endian layout: `tcpi_bytes_acked` u64 offset 120; `tcpi_snd_mss` u32 offset 16, `tcpi_lost` offset 32, `tcpi_rtt` offset 68, `tcpi_snd_cwnd` offset 80, `tcpi_total_retrans` offset 100. These offsets must be verified against the host's `/usr/include/linux/tcp.h` and kernel.

Plots alone (without re-running the experiment):

```bash
python3 plot_results.py --output output
```

## Docker

```bash
docker build -t cs422-assignment2 .
docker run --rm --network host -v "$PWD/data:/app/data:ro" -v "$PWD/output:/app/output" cs422-assignment2 -n 10 -d 60 -i 0.2
```

Docker shares the host kernel. The Dockerfile intentionally does not install or invoke iperf3. Test only against servers that permit public testing; do not run simultaneous high-volume experiments against shared public servers.

## Protocol

Control and data sockets each send the same 37-byte cookie (32 hex + `-` + 4 hex). The client receives PARAM_EXCHANGE (9), sends length-prefixed JSON parameters, receives CREATE_STREAMS (10), creates the data socket, receives TEST_START (1) and TEST_RUNNING (2), sends data, sends TEST_END (4), exchanges length-prefixed JSON results (EXCHANGE_RESULTS 13), receives DISPLAY_RESULTS (14), and sends IPERF_DONE (16). Server refusal, timeout, early EOF, and unexpected states are logged and bounded retries are attempted.

**Validation note:** This project has syntax/static tests, but an end-to-end live public-server test has not been run in the generation environment. Verify the handshake and result JSON against a reachable standard iperf3 server before submission. Public servers may use different iperf3 versions.
