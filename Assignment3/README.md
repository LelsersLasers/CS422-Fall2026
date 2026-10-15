# Assignment 3: Option 1

Design: [LaTeX](../Assignment2/part3b-writeup.tex)/[PDF](../Assignment2/part3b-writeup.pdf)

Run the commands below from the repository root unless stated otherwise.

## Implementation

* [kernel/tcp_rla.c](kernel/tcp_rla.c): contains the window controller,
registers `rla`, and supplies live socket state through Linux's
congestion-control callbacks

RLA retains:
* The kernel's initial window
* Normally ten segments
* Uses ACK-driven slow start

In congestion avoidance it evaluates once per `max(100 ms, starting SRTT)` epoch. Relative RTT inflation above 25% reduces cwnd to `max(2, floor(0.9*cwnd))` and ends slow start.
Below 10% inflation, an epoch with at least 80% utilization and a window-limited sender can add one segment. Otherwise it holds. The 10% and 25% comparisons are strict. The 80% comparison is inclusive. Window changes respect the kernel clamp.

Epoch utilization uses acknowledged bytes and the starting window/MSS/RTT:
`u = delta_bytes * starting_rtt_us / (elapsed_us * starting_cwnd * starting_mss)`.
The test `u >= 0.8` uses checked 64-bit multiplication. Overflow prevents
additive growth. The lifetime minimum is over positive SRTT observations made
by the normal-ACK controller, excluding recovery processing. `ssthresh` returns `max(2, floor(cwnd/2))` on native congestion events, including ECN.

Linux owns retransmission, PRR, timeout handling, pacing, and spurious-loss
undo. The normal controller does not halve once per retransmission. Epochs reset
on native recovery entry/exit, undo, and idle window restart. In the native
RTO loss state the adapter permits Reno-style restart, including the kernel's
temporary one-segment window. The module does not change the system-wide
default congestion controller or install a custom receiver.

## Build and load

Build against the configured development tree for the running kernel, including
its `Module.symvers`. The implementation has been compiled on x86-64 Linux
6.18.50 with GCC 15.2.0 and binutils 2.46. Required features include `CONFIG_INET`,
`CONFIG_MODULES`, and module unloading for cleanup.

On a system with matching kernel development files installed:

```bash
make -C Assignment3/kernel
sudo insmod Assignment3/kernel/tcp_rla.ko
cat /proc/sys/net/ipv4/tcp_available_congestion_control
sudo rmmod tcp_rla
```

`KDIR` defaults to `/lib/modules/$(uname -r)/build`. On the current NixOS host:

```bash
nix build '/nix/store/h8ljcxrnqc53n1ijm1kvd13d89aldgz0-linux-6.18.50.drv^dev' --no-link
make -C Assignment3/kernel \
  KDIR=/nix/store/csfizpd7wzbmcn8a6xzigy45xxzygw40-linux-6.18.50-dev/lib/modules/6.18.50/build \
  CC=/nix/store/hbsz2ngi9ixbhd9na1xagh2yc8qnmj7y-gcc-wrapper-15.2.0/bin/cc
```

Use the same `KDIR` with `make -C Assignment3/kernel clean` to remove build
artifacts. The module checks that its private state fits `ICSK_CA_PRIV_SIZE`.

Select `rla` on the data socket using `TCP_CONGESTION` before connecting when
integrating it into the Assignment 2 client. Repeated four-algorithm experiments,
plots, and aggregate analysis will be implemented later.
