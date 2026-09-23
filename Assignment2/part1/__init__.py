#!/usr/bin/env python3
"""Part 1: iPerf3 throughput client (socket program from scratch).

Modules:
    protocol   -- iPerf3 wire protocol (cookie, state bytes, length-prefixed JSON).
    tcp_stats  -- TCP_INFO decoding and goodput sample computation.
    utils      -- Server list loading, platform checks, CSV/JSON writers.
    run_test   -- Execute a single iPerf3 test against one server.
    run_iperf  -- Part-1 entry point: destination selection + test loop + output.
"""
