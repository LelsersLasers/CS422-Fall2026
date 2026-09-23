# CS 422 Assignment 2 — Part 1

Native Python socket implementation of an iperf3 TCP sender. It does **not** invoke the iperf3 binary. Requires Linux (including WSL2), Python 3.10+, matplotlib, and a real public iperf3 server list at `data/listed_iperf3_servers.json`.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 part1.py --servers data/listed_iperf3_servers.json -n 10 -d 60 -i 0.2 --max-attempts 30
```

For an initial smoke test use `-n 1 -d 3 -i 0.2`. For reproducible selection use `--seed 42`. `--algorithm cubic` is optional. Ports expressed as `9205-9240` are alternative ports of one destination; each is tried until success or the global attempt limit. Hosts are randomly shuffled. This implementation sends one TCP stream in normal (not reverse/UDP) mode; the OPTIONS column is informational only.

## Outputs

`summary.csv`: per-run min/median/mean/nearest-rank p95 of per-interval goodput (Mbit/s). `*_samples.csv`: timestamp, actual sampling interval, cumulative/delta acknowledged bytes, goodput, sender bytes, and kernel TCP stats. `*_server_results.json`: final iperf3 server result. `failures.csv`: failed attempts. `manifest.json`: selection, configuration, shortfall, kernel. `goodput.pdf`: per-destination time series.

The goodput numerator is **delta of Linux tcpi_bytes_acked** on the **data** socket, not application bytes passed to send(). The initial baseline is taken after TEST_RUNNING, so TCP handshake/cookie acknowledgments are excluded from the measured intervals. The final partial interval is retained. Samples are taken in the sender's event loop and therefore may be delayed under scheduling load; actual elapsed time is used in the denominator. TCP_INFO uses Linux native-endian layout: `tcpi_bytes_acked` u64 offset 120; `tcpi_snd_mss` u32 offset 16, `tcpi_lost` offset 32, `tcpi_rtt` offset 68, `tcpi_snd_cwnd` offset 80, `tcpi_total_retrans` offset 100. These offsets must be verified against the host's `/usr/include/linux/tcp.h` and kernel.

## Docker

```bash
docker build -t cs422-part1 .
docker run --rm --network host -v "$PWD/data:/app/data:ro" -v "$PWD/results:/app/results" cs422-part1 -n 10 -d 60 -i 0.2
```

Docker shares the host kernel. The Dockerfile intentionally does not install or invoke iperf3. Test only against servers that permit public testing; do not run simultaneous high-volume experiments against shared public servers.

## Protocol

Control and data sockets each send the same 37-byte cookie. The client receives PARAM_EXCHANGE, sends length-prefixed JSON parameters, receives CREATE_STREAMS, creates the data socket, receives TEST_START and TEST_RUNNING, sends data, sends TEST_END, exchanges length-prefixed JSON results, receives DISPLAY_RESULTS, and sends IPERF_DONE. Server refusal, timeout, early EOF, and unexpected states are logged and bounded retries are attempted.

**Validation note:** This project has syntax/static tests, but an end-to-end live public-server test has not been run in the generation environment. Verify the handshake and result JSON against a reachable standard iperf3 server before submission. Public servers may use different iperf3 versions.
