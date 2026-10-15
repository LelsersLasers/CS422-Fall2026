# Assignment 3: Option 1

Design: [LaTeX](../Assignment2/part3b-writeup.tex)/[PDF](../Assignment2/part3b-writeup.pdf)

Run the commands below from the repository root unless stated otherwise.

## Implementation

* [kernel/rla_controller.h](kernel/rla_controller.h): contains the integer window
controller (`rla_on_ack`, `rla_busy`, `rla_loss_window`)
* [kernel/tcp_rla.c](kernel/tcp_rla.c): registers `rla`
and supplies live socket state through Linux's congestion-control callbacks

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

