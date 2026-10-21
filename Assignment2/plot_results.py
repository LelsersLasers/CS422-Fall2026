"""
Generates the PDF visualizations from the CSV/JSON output written by the
part modules. All inputs and outputs live under the single ``output/``
directory:

    output/goodput.pdf       Part 1: goodput over time, one page per destination.
    output/tcp_stats.pdf     Part 2: representative destination time series
                             (snd cwnd, RTT, loss proxy, goodput) plus scatter
                             plots of cwnd/RTT/loss vs goodput.
    output/comparison.pdf    Part 3: CUBIC/Reno/BBR time series and scatter
                             plots overlaid for Part 2's representative
                             destination (plus per-algorithm pages), with
                             consistent axis scales, and box plots of
                             variability across runs and destinations.

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

ALGO_ORDER = ('cubic', 'reno', 'bbr')

# Fixed per-algorithm identity: color (colorblind-checked categorical
# palette) plus a line style and marker, so curves stay distinguishable in
# grayscale print.
ALGO_STYLE = {
    'cubic': {'color': '#2a78d6', 'linestyle': '-', 'marker': 'o'},
    'reno': {'color': '#eb6834', 'linestyle': '--', 'marker': 's'},
    'bbr': {'color': '#1baf7a', 'linestyle': ':', 'marker': '^'},
}


def _comparison_limits(traces: list[list[dict]]) -> tuple[dict, dict]:
    """Common axis limits across all algorithms' traces."""
    def peak(key, scale=1.0):
        return max(
            (v * scale for rows in traces for v in _col(rows, key)),
            default=0,
        )

    loss = max(
        (v for rows in traces for v in _col(rows, _loss_key(rows))),
        default=0,
    )
    ylims = {
        'snd_cwnd_segments': peak('snd_cwnd_segments') * 1.05,
        'rtt_ms': max(peak('rtt_us', 1e-3), peak('rttvar_us', 1e-3)) * 1.05,
        'loss_proxy': max(loss, 1) * 1.05,
        'goodput_mbps': peak('goodput_mbps') * 1.05,
    }
    xlims = {
        'snd_cwnd_segments': ylims['snd_cwnd_segments'],
        'rtt_ms': peak('rtt_us', 1e-3) * 1.05,
        'loss_proxy': ylims['loss_proxy'],
    }
    return xlims, ylims


def _overlay_time_series_page(
    first_runs: dict[str, list[dict]],
    title: str,
    xlim: tuple,
    ylims: dict,
) -> None:
    """cwnd, RTT, loss proxy, and goodput over time, one curve per algo."""
    panels = [
        ('snd_cwnd_segments', 1.0, 'Congestion window', 'cwnd (segments)'),
        ('rtt_us', 1e-3, 'Smoothed RTT', 'RTT (ms)'),
        (None, 1.0, 'Retransmissions in interval', 'Retransmitted segments'),
        ('goodput_mbps', 1.0, 'Acknowledged goodput', 'Goodput (Mbit/s)'),
    ]
    limit_keys = ['snd_cwnd_segments', 'rtt_ms', 'loss_proxy', 'goodput_mbps']

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, scale, panel_title, ylabel), limit_key in zip(
        axes.flat, panels, limit_keys
    ):
        for algo in ALGO_ORDER:
            rows = first_runs.get(algo)
            if not rows:
                continue
            style = ALGO_STYLE[algo]
            ys = [v * scale for v in _col(rows, key or _loss_key(rows))]
            ax.plot(
                _col(rows, 'elapsed_s'), ys,
                color=style['color'], linestyle=style['linestyle'],
                linewidth=1.5, label=algo,
            )
        ax.set(title=panel_title, xlabel='Elapsed time (s)', ylabel=ylabel)
        ax.set_xlim(*xlim)
        ax.set_ylim(bottom=0, top=ylims[limit_key] or None)
        ax.grid(alpha=0.3)
    axes[0, 0].legend(title='Algorithm')

    fig.suptitle(title)
    fig.tight_layout()


def _overlay_scatter_page(
    runs_by_algo: dict[str, list[list[dict]]],
    title: str,
    xlims: dict,
    ylims: dict,
) -> None:
    """cwnd, RTT, and loss signal vs goodput; every run, colored by algo."""
    panels = [
        ('snd_cwnd_segments', 1.0, 'Congestion window (segments)',
         'Congestion window vs goodput', 'snd_cwnd_segments'),
        ('rtt_us', 1e-3, 'Smoothed RTT (ms)', 'RTT vs goodput', 'rtt_ms'),
        (None, 1.0, 'Retransmissions in interval',
         'Retransmissions vs goodput', 'loss_proxy'),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    for ax, (key, scale, xlabel, panel_title, limit_key) in zip(axes, panels):
        for algo in ALGO_ORDER:
            style = ALGO_STYLE[algo]
            xs, ys = [], []
            for rows in runs_by_algo.get(algo, []):
                xs += [v * scale for v in _col(rows, key or _loss_key(rows))]
                ys += _col(rows, 'goodput_mbps')
            if not xs:
                continue
            ax.scatter(
                xs, ys, s=16, alpha=0.6, label=algo,
                color=style['color'], marker=style['marker'],
                edgecolors='white', linewidths=0.5,
            )
        ax.set(title=panel_title, xlabel=xlabel, ylabel='Goodput (Mbit/s)')
        ax.set_xlim(left=0, right=xlims[limit_key] or None)
        ax.set_ylim(bottom=0, top=ylims['goodput_mbps'] or None)
        ax.grid(alpha=0.3)
    axes[0].legend(title='Algorithm')

    fig.suptitle(title)
    fig.tight_layout()


def _variability_page(summary_rows: list[dict]) -> None:
    """Per-run results across all destinations and repetitions."""
    panels = [
        ('mean_mbps', 'Mean goodput per run', 'Goodput (Mbit/s)'),
        ('mean_rtt_ms', 'Mean RTT per run', 'RTT (ms)'),
        ('queueing_delay_ms', 'Queueing delay per run (mean RTT - min RTT)',
         'Delay (ms)'),
        ('retrans_pct', 'Retransmitted bytes per run', '% of bytes sent'),
    ]
    algos = [
        a for a in ALGO_ORDER
        if any(r['requested_algorithm'] == a for r in summary_rows)
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, panel_title, ylabel) in zip(axes.flat, panels):
        data = [
            [float(r[key]) for r in summary_rows
             if r['requested_algorithm'] == a and r.get(key) not in (None, '')]
            for a in algos
        ]
        box = ax.boxplot(data, patch_artist=True, widths=0.5)
        ax.set_xticks(range(1, len(algos) + 1), algos)
        for patch, algo in zip(box['boxes'], algos):
            patch.set_facecolor(ALGO_STYLE[algo]['color'])
            patch.set_alpha(0.35)
        for median in box['medians']:
            median.set_color('black')
        # Overlay each run so small sample counts stay visible.
        for i, (values, algo) in enumerate(zip(data, algos), start=1):
            ax.scatter(
                [i] * len(values), values, s=14, zorder=3,
                color=ALGO_STYLE[algo]['color'],
                marker=ALGO_STYLE[algo]['marker'],
                edgecolors='white', linewidths=0.5,
            )
        ax.set(title=panel_title, ylabel=ylabel)
        ax.margins(y=0.1)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3, axis='y')

    runs = len({r['repetition'] for r in summary_rows})
    dests = len({(r['host'], r['port']) for r in summary_rows})
    fig.suptitle(
        f'Variability across runs: {dests} destination(s) x {runs} '
        f'repetition(s), one point per test'
    )
    fig.tight_layout()


def plot_comparison(
    runs_by_algo: dict[str, list[list[dict]]],
    destination: str,
    summary_rows: list[dict],
    outdir: Path,
) -> Path:
    """Generate CUBIC/Reno/BBR comparison plots.

    Pages:
        1. Overlaid time series (cwnd, RTT, loss proxy, goodput) for the
           representative destination, first repetition of each algorithm.
        2. Overlaid scatter plots vs goodput, all repetitions at that
           destination.
        3+. The same two views per algorithm on separate pages.
        Last. Variability across runs and destinations (box plots).

    All algorithms share axis scales so differences can be compared directly.

    Args:
        runs_by_algo: algorithm -> list of sample traces (one per
            repetition, in repetition order) at the representative
            destination.
        destination: "host:port" label of the representative destination.
        summary_rows: Rows of part3/comparison_summary.csv.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / 'comparison.pdf'

    all_traces = [t for traces in runs_by_algo.values() for t in traces]
    if not all_traces:
        return output_path

    first_runs = {a: traces[0] for a, traces in runs_by_algo.items() if traces}
    max_elapsed = max(max(_col(rows, 'elapsed_s')) for rows in all_traces)
    xlims, ylims = _comparison_limits(all_traces)

    with PdfPages(output_path) as pdf:
        _overlay_time_series_page(
            first_runs,
            f'CUBIC vs Reno vs BBR: {destination} (repetition 1)',
            (0, max_elapsed),
            ylims,
        )
        pdf.savefig(plt.gcf())
        plt.close('all')

        reps = max(len(t) for t in runs_by_algo.values())
        _overlay_scatter_page(
            runs_by_algo,
            f'CUBIC vs Reno vs BBR: {destination} '
            f'(all {reps} repetition(s))',
            xlims,
            ylims,
        )
        pdf.savefig(plt.gcf())
        plt.close('all')

        for algo in ALGO_ORDER:
            rows = first_runs.get(algo)
            if not rows:
                continue
            title = f'Congestion control: {algo} ({destination}, repetition 1)'
            _time_series_page(
                rows, title, xlim=(0, max_elapsed), ylims=ylims,
            )
            pdf.savefig(plt.gcf())
            plt.close('all')

            _scatter_page(rows, title, xlims=xlims, ylims=ylims)
            pdf.savefig(plt.gcf())
            plt.close('all')

        if summary_rows:
            _variability_page(summary_rows)
            pdf.savefig(plt.gcf())
            plt.close('all')

    return output_path


def _part3_destination(
    summary_rows: list[dict],
    output_dir: Path,
) -> tuple[str, str] | None:
    """Representative destination for the Part 3 comparison.

    Prefer Part 2's representative destination (so Parts 2 and 3 plot the
    same path); otherwise the destination with the most successful tests
    across the most algorithms.
    """
    covered: dict[tuple[str, str], set] = {}
    counts: dict[tuple[str, str], int] = {}
    for row in summary_rows:
        key = (row['host'], str(row['port']))
        covered.setdefault(key, set()).add(row['requested_algorithm'])
        counts[key] = counts.get(key, 0) + 1
    if not covered:
        return None

    rep_json = output_dir / 'representative.json'
    if rep_json.exists():
        rep = json.loads(rep_json.read_text())
        key = (rep['host'], str(rep['port']))
        if len(covered.get(key, ())) == max(len(a) for a in covered.values()):
            return key

    return max(covered, key=lambda k: (len(covered[k]), counts[k]))


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
        comparison_rows = _load_csv(comparison_summary)
        destination = _part3_destination(comparison_rows, output_dir)

        # One trace per repetition, per algorithm, at that destination.
        runs_by_algo: dict[str, list[list[dict]]] = {}
        ordered = sorted(
            comparison_rows, key=lambda r: int(r.get('repetition') or 0)
        )
        for row in ordered:
            if (row['host'], str(row['port'])) != destination:
                continue
            algo = row['requested_algorithm']
            samples_path = part3_dir / algo / f"{row['run_id']}_samples.csv"
            if samples_path.exists():
                runs_by_algo.setdefault(algo, []).append(
                    _load_csv(samples_path)
                )

        if runs_by_algo:
            generated.append(
                plot_comparison(
                    runs_by_algo,
                    f'{destination[0]}:{destination[1]}',
                    comparison_rows,
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