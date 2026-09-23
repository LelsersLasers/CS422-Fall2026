#!/usr/bin/env python3
"""Unified plotter for Assignment 2 (all three parts).

Generates the PDF visualizations from the CSV/JSON output written by the
part modules. All inputs and outputs live under the single ``output/``
directory:

    output/goodput.pdf       Part 1: goodput over time, one page per destination.
    output/tcp_stats.pdf     Part 2: representative destination time series
                             (snd cwnd, RTT, loss proxy, goodput) plus scatter
                             plots of cwnd/RTT/loss vs goodput.
    output/comparison.pdf    Part 3: per-algorithm (CUBIC/Reno/BBR) time series
                             and scatter plots for the same destination, with
                             consistent axis scales across algorithms.

Usage:
    python3 plot_results.py            # plots from ./output
    python3 plot_results.py --output output
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless PDF generation.
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


# ----------------------------------------------------------------------
# CSV loading helpers
# ----------------------------------------------------------------------

def _load_csv(path: Path) -> list[dict]:
    """Read a CSV file into a list of row dicts (string values)."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _col(rows: list[dict], key: str) -> list[float]:
    """Extract a numeric column as floats, skipping rows without the key."""
    return [float(r[key]) for r in rows if r.get(key) not in (None, '')]


# ----------------------------------------------------------------------
# Part 1: goodput over time
# ----------------------------------------------------------------------

def plot_goodput(runs: list[tuple[dict, list[dict]]], outdir: Path) -> Path:
    """Goodput-over-time plot, one page per destination.

    Args:
        runs: List of (summary_row, samples) tuples.
        outdir: Directory to write the PDF to.

    Returns:
        Path to the generated PDF.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / 'goodput.pdf'

    with PdfPages(output_path) as pdf:
        for summary, rows in runs:
            if not rows:
                continue
            elapsed = _col(rows, 'elapsed_s')
            speeds = _col(rows, 'goodput_mbps')

            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(elapsed, speeds, marker='.', markersize=3, linewidth=0.8)
            ax.set(
                title=(
                    f"{summary['host']}:{summary['port']} — "
                    f"{summary['algorithm']} "
                    f"(mean {summary['mean_mbps']:.2f} Mbit/s)"
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


# ----------------------------------------------------------------------
# Part 2: TCP stats of the representative destination
# ----------------------------------------------------------------------

def _time_series_page(rows: list[dict], title: str,
                      xlim: tuple | None = None,
                      ylims: dict | None = None) -> None:
    """One page: cwnd, RTT, loss proxy, and goodput vs elapsed time."""
    xlim = xlim or None
    ylims = ylims or {}
    elapsed = _col(rows, 'elapsed_s')

    panels = [
        ('snd_cwnd_segments', 'Congestion window (segments)', 0),
        ('rtt_us', 'Smoothed RTT (us)', 0),
        ('total_retrans', 'Retransmitted segments (cumulative)', 0),
        ('goodput_mbps', 'Acknowledged goodput (Mbit/s)', 0),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, label, bottom) in zip(axes.flat, panels):
        ax.plot(elapsed, _col(rows, key), linewidth=0.8)
        ax.set(title=label, xlabel='Elapsed time (s)')
        ax.set_ylim(bottom=bottom)
        if xlim:
            ax.set_xlim(*xlim)
        if key in ylims:
            ax.set_ylim(bottom=0, top=ylims[key])
        ax.grid(alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()


def _scatter_page(rows: list[dict], title: str,
                  xlims: dict | None, ylims: dict | None) -> None:
    """One page: cwnd/RTT/loss vs goodput scatter plots."""
    xlims = xlims or {}
    ylims = ylims or {}
    goodput = _col(rows, 'goodput_mbps')
    cwnd = _col(rows, 'snd_cwnd_segments')
    rtt = _col(rows, 'rtt_us')
    loss = _col(rows, 'total_retrans')

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    pairs = [
        (cwnd, 'Congestion window (segments)', 'snd_cwnd_segments',
         'Congestion window vs goodput'),
        (rtt, 'Smoothed RTT (us)', 'rtt_us', 'RTT vs goodput'),
        (loss, 'Retransmitted segments (cumulative)', 'total_retrans',
         'Loss proxy vs goodput'),
    ]
    for ax, (xs, xlab, key, title) in zip(axes, pairs):
        ax.scatter(xs, goodput, s=6, alpha=0.5)
        ax.set(title=title, xlabel=xlab,
               ylabel='Goodput (Mbit/s)')
        ax.set_ylim(bottom=0)
        if key in xlims:
            ax.set_xlim(*xlims[key])
        if 'goodput_mbps' in ylims:
            ax.set_ylim(bottom=0, top=ylims['goodput_mbps'])
        ax.grid(alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()


def plot_tcp_stats(rows: list[dict], rep: dict, outdir: Path) -> Path:
    """Part 2 PDF: representative-destination TCP stats time series + scatter.

    Args:
        rows: Representative run's per-interval sample rows.
        rep: Representative summary dict (host/port/algorithm/run_id).
        outdir: Directory to write the PDF to.

    Returns:
        Path to the generated PDF.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / 'tcp_stats.pdf'
    title = (
        f"TCP stats — {rep['host']}:{rep['port']} "
        f"({rep['algorithm']}, run {rep['run_id']})"
    )

    with PdfPages(output_path) as pdf:
        _time_series_page(rows, title)
        pdf.savefig(plt.gcf())
        plt.close('all')

        _scatter_page(rows, title)
        pdf.savefig(plt.gcf())
        plt.close('all')

    return output_path


# ----------------------------------------------------------------------
# Part 3: algorithm comparison
# ----------------------------------------------------------------------

def plot_comparison(by_algo: dict[str, list[dict]], outdir: Path) -> Path:
    """Part 3 PDF: per-algorithm time series and scatter plots.

    All algorithms are plotted on the same destination with consistent
    axis scales (max across algorithms per metric) so the panels can be
    compared directly.

    Args:
        by_algo: Mapping of algorithm name -> sample rows for the
            representative destination.
        outdir: Directory to write the PDF to.

    Returns:
        Path to the generated PDF.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / 'comparison.pdf'

    # Consistent axis scales across algorithms.
    max_elapsed = max(
        (max(_col(rows, 'elapsed_s')) for rows in by_algo.values() if rows),
        default=None,
    )
    ylims = {}
    for key in ('snd_cwnd_segments', 'rtt_us', 'goodput_mbps'):
        vals = [v for rows in by_algo.values() for v in _col(rows, key)]
        if vals:
            ylims[key] = max(vals)
    xlims = {}
    for key in ('snd_cwnd_segments', 'rtt_us'):
        vals = [v for rows in by_algo.values() for v in _col(rows, key)]
        if vals:
            xlims[key] = (0, max(vals))

    with PdfPages(output_path) as pdf:
        for algo in ('cubic', 'reno', 'bbr'):
            rows = by_algo.get(algo)
            if not rows:
                continue
            title = f"Congestion control: {algo}"
            _time_series_page(rows, title, (0, max_elapsed), ylims)
            pdf.savefig(plt.gcf())
            plt.close('all')

            _scatter_page(rows, title, xlims, ylims)
            pdf.savefig(plt.gcf())
            plt.close('all')

    return output_path


# ----------------------------------------------------------------------
# Orchestration: discover outputs and generate every PDF
# ----------------------------------------------------------------------

def run_plot_results(output_dir: Path = Path('output')) -> list[Path]:
    """Generate all Assignment 2 plots from the outputs in ``output_dir``.

    Expected inputs:
        output/summary.csv + output/{run_id}_samples.csv        (Part 1)
        output/representative_samples.csv + representative.json (Part 2)
        output/part3/comparison_summary.csv + part3/{algo}/     (Part 3)

    Returns:
        List of generated PDF paths (skips a plot when its inputs are absent).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    # ------------------------------------------------------------------
    # Part 1: goodput per destination
    # ------------------------------------------------------------------
    summary_path = output_dir / 'summary.csv'
    if summary_path.exists():
        runs = []
        for s in _load_csv(summary_path):
            samples_path = output_dir / f"{s['run_id']}_samples.csv"
            if samples_path.exists():
                runs.append((s, _load_csv(samples_path)))
        if runs:
            generated.append(plot_goodput(runs, output_dir))

    # ------------------------------------------------------------------
    # Part 2: representative TCP stats
    # ------------------------------------------------------------------
    rep_path = output_dir / 'representative_samples.csv'
    rep_json = output_dir / 'representative.json'
    if rep_path.exists() and rep_json.exists():
        rows = _load_csv(rep_path)
        rep = json.loads(rep_json.read_text())
        generated.append(plot_tcp_stats(rows, rep, output_dir))

    # ------------------------------------------------------------------
    # Part 3: algorithm comparison (representative destination, all algos)
    # ------------------------------------------------------------------
    part3_dir = output_dir / 'part3'
    part3_cmp = part3_dir / 'comparison_summary.csv'
    if part3_cmp.exists():
        cmp_rows = _load_csv(part3_cmp)
        by_dest: dict[tuple[str, str], dict[str, list[dict]]] = {}
        for r in cmp_rows:
            algo = r['requested_algorithm']
            samples_path = (
                part3_dir / algo / f"{r['run_id']}_samples.csv"
            )
            if not samples_path.exists():
                continue
            by_dest.setdefault((r['host'], r['port']), {}).setdefault(
                algo, []
            )
            by_dest[(r['host'], r['port'])][algo].extend(
                _load_csv(samples_path)
            )

        if by_dest:
            # Representative destination for comparison: the one covered by
            # the most algorithms, ties broken by total mean goodput.
            def _score(item):
                _, algos = item
                means = [
                    max(_col(rows, 'goodput_mbps'))
                    for rows in algos.values() if rows
                ]
                return len(algos), sum(means)

            _, by_algo = max(by_dest.items(), key=_score)
            generated.append(plot_comparison(by_algo, output_dir))

    return generated


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        '--output', type=Path, default=Path('output'),
        help='Directory containing experiment outputs (default: output)',
    )
    args = p.parse_args()

    pdfs = run_plot_results(args.output)
    if not pdfs:
        print('No inputs found; nothing plotted.')
        return 1
    for pdf in pdfs:
        print(f'Wrote {pdf}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
