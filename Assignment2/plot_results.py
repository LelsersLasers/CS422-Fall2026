"""
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
    python3 plot_results.py
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
    """Read a CSV file into a list of row dictionaries."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _col(rows: list[dict], key: str) -> list[float]:
    """Extract a numeric column as floats, skipping missing values."""
    return [
        float(row[key])
        for row in rows
        if row.get(key) not in (None, '')
    ]


def _fmt_float(value, spec: str = '.2f') -> str:
    """Format a numeric value while tolerating CSV strings/blanks."""
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return str(value) if value not in (None, '') else 'n/a'


def _has_column(rows: list[dict], key: str) -> bool:
    """Return True when the CSV rows contain a given field."""
    return bool(rows) and key in rows[0]


def _loss_key(rows: list[dict]) -> str:
    """Choose the best available loss/retransmission signal.

    New traces contain delta_retrans, which measures retransmissions
    occurring during the current sampling interval. Older traces contain
    only total_retrans, so retain compatibility with those files.
    """
    if _has_column(rows, 'delta_retrans'):
        return 'delta_retrans'

    return 'total_retrans'


def _loss_label(rows: list[dict]) -> str:
    """Human-readable label for the selected loss proxy."""
    if _loss_key(rows) == 'delta_retrans':
        return 'Retransmissions in interval'

    return 'Cumulative retransmissions'


# ----------------------------------------------------------------------
# Part 1: goodput over time
# ----------------------------------------------------------------------

def plot_goodput(
    runs: list[tuple[dict, list[dict]]],
    outdir: Path,
) -> Path:
    """Goodput-over-time plot, one page per destination."""
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / 'goodput.pdf'

    with PdfPages(output_path) as pdf:
        for summary, rows in runs:
            if not rows:
                continue

            elapsed = _col(rows, 'elapsed_s')
            speeds = _col(rows, 'goodput_mbps')

            fig, ax = plt.subplots(figsize=(9, 4))

            ax.plot(
                elapsed,
                speeds,
                marker='.',
                markersize=3,
                linewidth=0.8,
            )

            ax.set(
                title=(
                    f"{summary['host']}:{summary['port']} — "
                    f"{summary['algorithm']} "
                    f"(mean "
                    f"{_fmt_float(summary.get('mean_mbps'))} Mbit/s)"
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
# Shared TCP-stat visualization helpers
# ----------------------------------------------------------------------

def _time_series_page(
    rows: list[dict],
    title: str,
    xlim: tuple | None = None,
    ylims: dict | None = None,
) -> None:
    """Plot cwnd, RTT, loss proxy, and goodput over time."""
    ylims = ylims or {}

    elapsed = _col(rows, 'elapsed_s')
    cwnd = _col(rows, 'snd_cwnd_segments')

    # TCP_INFO reports RTT values in microseconds.
    rtt_ms = [
        value / 1000.0
        for value in _col(rows, 'rtt_us')
    ]

    # rttvar is recommended by the assignment but older traces may not
    # contain it, so treat it as optional.
    if _has_column(rows, 'rttvar_us'):
        rttvar_ms = [
            value / 1000.0
            for value in _col(rows, 'rttvar_us')
        ]
    else:
        rttvar_ms = []

    loss_key = _loss_key(rows)
    loss = _col(rows, loss_key)

    goodput = _col(rows, 'goodput_mbps')

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))

    # --------------------------------------------------------------
    # Congestion window
    # --------------------------------------------------------------
    ax = axes[0, 0]

    ax.plot(
        elapsed,
        cwnd,
        linewidth=0.8,
    )

    ax.set(
        title='Congestion window',
        xlabel='Elapsed time (s)',
        ylabel='cwnd (segments)',
    )

    if ylims.get('snd_cwnd_segments', 0) > 0:
        ax.set_ylim(
            bottom=0,
            top=ylims['snd_cwnd_segments'],
        )
    else:
        ax.set_ylim(bottom=0)

    # --------------------------------------------------------------
    # RTT
    # --------------------------------------------------------------
    ax = axes[0, 1]

    ax.plot(
        elapsed,
        rtt_ms,
        linewidth=0.8,
        label='SRTT',
    )

    if rttvar_ms:
        ax.plot(
            elapsed,
            rttvar_ms,
            linewidth=0.8,
            label='RTT variation',
        )

    ax.set(
        title='RTT',
        xlabel='Elapsed time (s)',
        ylabel='RTT (ms)',
    )

    ax.legend()

    if ylims.get('rtt_ms', 0) > 0:
        ax.set_ylim(
            bottom=0,
            top=ylims['rtt_ms'],
        )
    else:
        ax.set_ylim(bottom=0)

    # --------------------------------------------------------------
    # Loss / retransmission signal
    # --------------------------------------------------------------
    ax = axes[1, 0]

    ax.plot(
        elapsed,
        loss,
        marker='.',
        markersize=4,
        linewidth=0.8,
    )

    ax.set(
        title=_loss_label(rows),
        xlabel='Elapsed time (s)',
        ylabel='Retransmitted segments',
    )

    if ylims.get('loss_proxy', 0) > 0:
        ax.set_ylim(
            bottom=0,
            top=ylims['loss_proxy'],
        )
    else:
        ax.set_ylim(bottom=0)

    # --------------------------------------------------------------
    # Goodput
    # --------------------------------------------------------------
    ax = axes[1, 1]

    ax.plot(
        elapsed,
        goodput,
        linewidth=0.8,
    )

    ax.set(
        title='Acknowledged goodput',
        xlabel='Elapsed time (s)',
        ylabel='Goodput (Mbit/s)',
    )

    if ylims.get('goodput_mbps', 0) > 0:
        ax.set_ylim(
            bottom=0,
            top=ylims['goodput_mbps'],
        )
    else:
        ax.set_ylim(bottom=0)

    # Shared formatting.
    for ax in axes.flat:
        if xlim:
            ax.set_xlim(*xlim)

        ax.grid(alpha=0.3)

    fig.suptitle(title)
    fig.tight_layout()


def _scatter_page(
    rows: list[dict],
    title: str,
    xlims: dict | None = None,
    ylims: dict | None = None,
) -> None:
    """Plot cwnd, RTT, and loss signal against interval goodput."""
    xlims = xlims or {}
    ylims = ylims or {}

    goodput = _col(rows, 'goodput_mbps')
    cwnd = _col(rows, 'snd_cwnd_segments')

    rtt_ms = [
        value / 1000.0
        for value in _col(rows, 'rtt_us')
    ]

    loss_key = _loss_key(rows)
    loss = _col(rows, loss_key)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    plots = [
        (
            axes[0],
            cwnd,
            'Congestion window (segments)',
            'Congestion window vs goodput',
            'snd_cwnd_segments',
        ),
        (
            axes[1],
            rtt_ms,
            'Smoothed RTT (ms)',
            'RTT vs goodput',
            'rtt_ms',
        ),
        (
            axes[2],
            loss,
            _loss_label(rows),
            'Retransmissions vs goodput',
            'loss_proxy',
        ),
    ]

    for ax, xs, xlabel, plot_title, limit_key in plots:
        ax.scatter(
            xs,
            goodput,
            s=12,
            alpha=0.6,
        )

        ax.set(
            title=plot_title,
            xlabel=xlabel,
            ylabel='Goodput (Mbit/s)',
        )

        if xlims.get(limit_key, 0) > 0:
            ax.set_xlim(
                left=0,
                right=xlims[limit_key],
            )

        if ylims.get('goodput_mbps', 0) > 0:
            ax.set_ylim(
                bottom=0,
                top=ylims['goodput_mbps'],
            )
        else:
            ax.set_ylim(bottom=0)

        ax.grid(alpha=0.3)

    fig.suptitle(title)
    fig.tight_layout()


# ----------------------------------------------------------------------
# Part 2: TCP stats of representative destination
# ----------------------------------------------------------------------

def plot_tcp_stats(
    rows: list[dict],
    rep: dict,
    outdir: Path,
) -> Path:
    """Generate the Part 2 TCP statistics PDF.

    Page 1:
        Time series of cwnd, RTT/rttvar, retransmission signal,
        and acknowledged goodput.

    Page 2:
        Scatter plots of cwnd, RTT, and retransmissions against goodput.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    output_path = outdir / 'tcp_stats.pdf'

    title = (
        f"TCP stats — {rep['host']}:{rep['port']} "
        f"({rep['algorithm']}, run {rep['run_id']})"
    )

    with PdfPages(output_path) as pdf:
        _time_series_page(
            rows,
            title,
        )

        pdf.savefig(plt.gcf())
        plt.close('all')

        _scatter_page(
            rows,
            title,
        )

        pdf.savefig(plt.gcf())
        plt.close('all')

    return output_path


# ----------------------------------------------------------------------
# Part 3: algorithm comparison
# ----------------------------------------------------------------------

def plot_comparison(
    by_algo: dict[str, list[dict]],
    outdir: Path,
) -> Path:
    """Generate CUBIC/Reno/BBR comparison plots.

    All algorithms use common axis scales so differences can be visually
    compared directly.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    output_path = outdir / 'comparison.pdf'

    nonempty_runs = [
        rows
        for rows in by_algo.values()
        if rows
    ]

    if not nonempty_runs:
        return output_path

    # --------------------------------------------------------------
    # Find common X/Y limits across all algorithms.
    # --------------------------------------------------------------

    max_elapsed = max(
        max(_col(rows, 'elapsed_s'))
        for rows in nonempty_runs
    )

    all_cwnd = [
        value
        for rows in nonempty_runs
        for value in _col(rows, 'snd_cwnd_segments')
    ]

    all_rtt_ms = [
        value / 1000.0
        for rows in nonempty_runs
        for value in _col(rows, 'rtt_us')
    ]

    all_rttvar_ms = [
        value / 1000.0
        for rows in nonempty_runs
        if _has_column(rows, 'rttvar_us')
        for value in _col(rows, 'rttvar_us')
    ]

    all_goodput = [
        value
        for rows in nonempty_runs
        for value in _col(rows, 'goodput_mbps')
    ]

    all_loss = []

    for rows in nonempty_runs:
        loss_key = _loss_key(rows)
        all_loss.extend(_col(rows, loss_key))

    ylims = {
        'snd_cwnd_segments': max(all_cwnd, default=0),
        'rtt_ms': max(
            all_rtt_ms + all_rttvar_ms,
            default=0,
        ),
        'loss_proxy': max(all_loss, default=0),
        'goodput_mbps': max(all_goodput, default=0),
    }

    xlims = {
        'snd_cwnd_segments': max(all_cwnd, default=0),
        'rtt_ms': max(all_rtt_ms, default=0),
        'loss_proxy': max(all_loss, default=0),
    }

    # --------------------------------------------------------------
    # Generate pages in fixed algorithm order.
    # --------------------------------------------------------------

    with PdfPages(output_path) as pdf:
        for algo in ('cubic', 'reno', 'bbr'):
            rows = by_algo.get(algo)

            if not rows:
                continue

            title = f"Congestion control: {algo}"

            _time_series_page(
                rows,
                title,
                xlim=(0, max_elapsed),
                ylims=ylims,
            )

            pdf.savefig(plt.gcf())
            plt.close('all')

            _scatter_page(
                rows,
                title,
                xlims=xlims,
                ylims=ylims,
            )

            pdf.savefig(plt.gcf())
            plt.close('all')

    return output_path


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------

def run_plot_results(
    output_dir: Path = Path('output'),
) -> list[Path]:
    """Generate all Assignment 2 PDFs from experiment outputs."""
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated: list[Path] = []

    # --------------------------------------------------------------
    # Part 1
    # --------------------------------------------------------------

    summary_path = output_dir / 'summary.csv'

    if summary_path.exists():
        runs = []

        for summary in _load_csv(summary_path):
            samples_path = (
                output_dir
                / f"{summary['run_id']}_samples.csv"
            )

            if samples_path.exists():
                runs.append(
                    (
                        summary,
                        _load_csv(samples_path),
                    )
                )

        if runs:
            generated.append(
                plot_goodput(
                    runs,
                    output_dir,
                )
            )

    # --------------------------------------------------------------
    # Part 2
    # --------------------------------------------------------------

    representative_samples = (
        output_dir
        / 'representative_samples.csv'
    )

    representative_json = (
        output_dir
        / 'representative.json'
    )

    if (
        representative_samples.exists()
        and representative_json.exists()
    ):
        rows = _load_csv(
            representative_samples
        )

        rep = json.loads(
            representative_json.read_text()
        )

        generated.append(
            plot_tcp_stats(
                rows,
                rep,
                output_dir,
            )
        )

    # --------------------------------------------------------------
    # Part 3
    # --------------------------------------------------------------

    part3_dir = output_dir / 'part3'

    comparison_summary = (
        part3_dir
        / 'comparison_summary.csv'
    )

    if comparison_summary.exists():
        comparison_rows = _load_csv(
            comparison_summary
        )

        by_dest: dict[
            tuple[str, str],
            dict[str, list[dict]],
        ] = {}

        for row in comparison_rows:
            algo = row['requested_algorithm']

            samples_path = (
                part3_dir
                / algo
                / f"{row['run_id']}_samples.csv"
            )

            if not samples_path.exists():
                continue

            destination = (
                row['host'],
                row['port'],
            )

            by_dest.setdefault(
                destination,
                {},
            ).setdefault(
                algo,
                [],
            )

            by_dest[destination][algo].extend(
                _load_csv(samples_path)
            )

        if by_dest:

            # Prefer a destination covered by the largest number of
            # congestion-control algorithms.
            def _score(item):
                _, algorithms = item

                means = [
                    max(
                        _col(
                            rows,
                            'goodput_mbps',
                        )
                    )
                    for rows in algorithms.values()
                    if rows
                ]

                return (
                    len(algorithms),
                    sum(means),
                )

            _, by_algo = max(
                by_dest.items(),
                key=_score,
            )

            generated.append(
                plot_comparison(
                    by_algo,
                    output_dir,
                )
            )

    return generated


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('output'),
        help=(
            'Directory containing experiment outputs '
            '(default: output)'
        ),
    )

    args = parser.parse_args()

    pdfs = run_plot_results(
        args.output
    )

    if not pdfs:
        print(
            'No inputs found; nothing plotted.'
        )
        return 1

    for pdf in pdfs:
        print(f'Wrote {pdf}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())