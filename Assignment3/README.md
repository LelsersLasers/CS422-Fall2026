# Assignment 3: RLA kernel module

[kernel/tcp_rla.c](kernel/tcp_rla.c) implements RTT–Loss AIMD (RLA).
It uses RTT, loss feedback, and acknowledged throughput to adjust the congestion
window. The design is explained in the Assignment 2
[writeup PDF](../Assignment2/part3b-writeup.pdf) and
[LaTeX source](../Assignment2/part3b-writeup.tex).

Run the following commands from the repository root on a **Linux machine or
Linux virtual machine**. 
## Build

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

## Load and unload

```bash
# Check that the module's kernel version matches uname -r.
modinfo -F vermagic Assignment3/kernel/tcp_rla.ko
uname -r

# Register RLA and check that it appears in the available algorithms.
sudo insmod Assignment3/kernel/tcp_rla.ko
cat /proc/sys/net/ipv4/tcp_available_congestion_control

# Unload when finished.
sudo rmmod tcp_rla
```


## Python Evaluation

The evaluation compares RLA, CUBIC, Reno, and BBR using the TCP testing code from Assignment 2.

Make sure all four algorithms are available and `matplotlib` is installed.

### Run

From the repository root:

```bash
python3 Assignment3/run_evaluation.py
```

By default, this runs 3 repetitions across 3 destinations, with 10-second tests and 0.2-second sampling.

Results and plots are saved to `Assignment3/output/evaluation/`.

### Output

- `trials.csv` — Individual test results
- `aggregate.csv` — Throughput, RTT, and retransmission statistics
- `comparison.pdf` — Comparison graphs
- `manifest.json` — Experiment configuration
- `run_01/` to `run_03/` — Raw measurements

### Regenerate Plots

To regenerate plots without rerunning experiments:

```bash
python3 Assignment3/plot_evaluation.py --output Assignment3/output/evaluation
```

**Note:** To run another evaluation without overwriting existing results, specify a different directory using `--output`.


