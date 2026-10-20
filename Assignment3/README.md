# Assignment 3: RLA kernel module

[kernel/tcp_rla.c](kernel/tcp_rla.c) implements RTT–Loss AIMD (RLA).
It uses RTT, loss feedback, and acknowledged throughput to adjust the congestion
window. The design is explained in the Assignment 2
[writeup PDF](../Assignment2/part3b-writeup.pdf) and
[LaTeX source](../Assignment2/part3b-writeup.tex).

Run the following commands from the repository root on a **Linux machine or
Linux virtual machine**. 

## 1. Build the Kernel Module

Install a C compiler, make, kernel-module utilities, and the development files
for the kernel currently running. On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install build-essential kmod "linux-headers-$(uname -r)"
make -C Assignment3/kernel
```

This creates `Assignment3/kernel/tcp_rla.ko`, the loadable module. If the package
manager cannot find headers for your running kernel, use a distribution kernel
with matching headers available, or obtain the development files from whoever
provided that kernel.

On other distributions, install the equivalent packages. The Makefile uses
`/lib/modules/$(uname -r)/build` by default. If your development files are
elsewhere, set `KDIR`; if the kernel requires a different compiler, set `CC`:

```bash
make -C Assignment3/kernel KDIR=/path/to/kernel/build CC=gcc
```

It has been tested with x86-64 Linux 6.18.50, GCC 15.2.0, binutils 2.46.

## 2. Load and Kernel Module

Verify the module's kernel version:

```bash
modinfo -F vermagic Assignment3/kernel/tcp_rla.ko
uname -r
```

Load RLA:

```bash
sudo insmod Assignment3/kernel/tcp_rla.ko
```

If BBR is not available, load it:

```bash
sudo modprobe tcp_bbr
```

Verify the available congestion-control algorithms:

```bash
cat /proc/sys/net/ipv4/tcp_available_congestion_control
```

The output should include `rla`, `cubic`, `reno`, and `bbr`.

**Keep RLA loaded while running the experiments.**

## 3. Python Evaluation Setup

The evaluation compares RLA, CUBIC, Reno, and BBR using the TCP testing code from Assignment 2.

For additional environment setup instructions, see the [Assignment 2 README](../Assignment2/README.md).

From the repository root, create a Python virtual environment and install dependencies:

```bash
sudo apt-get install python3-venv
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r Assignment2/requirements.txt
```

The evaluation uses the Linux kernel's TCP congestion-control implementations. The Assignment 2 Docker helper runs Assignment 2, not this Assignment 3 evaluation. Run the commands below directly on Linux or WSL2 with the required kernel modules available.

## 4. Run the Evaluation

From the repository root:

```bash
python3 Assignment3/main.py
```

The default configuration:

- Compares RLA, CUBIC, Reno, and BBR.
- Tests 3 reachable destinations.
- Performs 3 repetitions per algorithm and destination.
- Runs each test for 10 seconds.
- Samples TCP statistics every 0.2 seconds.
- Automatically generates aggregate statistics and comparison plots after successful experiments.

Results are saved in `Assignment3/output/evaluation/`.

### Generated Outputs

- `trials.csv` — Individual test results.
- `aggregate.csv` — Goodput, RTT, and retransmission statistics.
- `comparison.pdf` — Time-series and scatter plots comparing all four algorithms.
- `manifest.json` — Experiment settings, test order, and execution details.
- `run_01/` to `run_03/` — Raw measurements from each repetition.
- `selection/` — Destination-selection measurements.

### Custom Configuration

To change the experiment settings:

```bash
python3 Assignment3/main.py \
  --destinations 3 \
  --repetitions 3 \
  --duration 10 \
  --interval 0.2 \
  --output Assignment3/output/custom_run
```

### Regenerate Plots

To regenerate plots and aggregate statistics without repeating the experiments:

```bash
python3 Assignment3/plot_evaluation.py \
  --output Assignment3/output/evaluation
```

**Note:** The runner does not overwrite existing experimental results. Use `--output` with a new directory when repeating experiments.

Public iperf3 servers may be busy or unavailable. Failed or incomplete experiments may require a new run.

Generated output files are excluded from Git tracking.

## 5. Unload the Kernel Module

After finishing the experiments:

```bash
sudo rmmod tcp_rla
```
