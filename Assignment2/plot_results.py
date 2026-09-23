#!/usr/bin/env python3
"""Visualization module for iPerf3 throughput test results.

Generates PDF plots of goodput over time for each successful test run.
"""

from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for PDF generation.
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def plot_goodput(runs: list[dict], outdir: Path) -> Path:
    """Generate a PDF with goodput-over-time plots for each successful run.

    Each run gets its own page in the PDF. The plot shows goodput (Mbit/s)
    on the Y-axis and elapsed time (seconds) on the X-axis.

    Args:
        runs: List of dicts, each containing:
            - 'trace': List of sample dicts with 'elapsed_s' and 'goodput_mbps'.
            - 'host', 'port', 'algorithm', 'run_id' for the title.
        outdir: Directory to write the PDF to.

    Returns:
        Path to the generated PDF file.
    """
    output_path = outdir / 'goodput.pdf'

    with PdfPages(output_path) as pdf:
        for run in runs:
            trace = run.get('trace', [])
            if not trace:
                continue

            fig, ax = plt.subplots(figsize=(9, 4))

            elapsed = [s['elapsed_s'] for s in trace]
            speeds = [s['goodput_mbps'] for s in trace]

            ax.plot(elapsed, speeds, marker='.', markersize=3, linewidth=0.8)
            ax.set(
                title=(
                    f"{run['host']}:{run['port']} — "
                    f"{run['algorithm']} ({run['run_id']})"
                ),
                xlabel='Elapsed time (s)',
                ylabel='Acknowledged goodput (Mbit/s)',
            )
            ax.set_ylim(bottom=0)
            ax.grid(alpha=0.3)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    return output_path
