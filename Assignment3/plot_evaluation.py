#!/usr/bin/env python3
"""Plot Assignment 3 repeated trials with common axes and complete-case matching."""
import argparse
import csv
import json
import statistics
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Assignment2'))
from plot_results import _time_series_page, _scatter_page, _col, _loss_key, _load_csv  # noqa: E402
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ALGORITHMS = ('rla', 'cubic', 'reno', 'bbr')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'Assignment3/output/evaluation')
    parser.add_argument('--destination', help='Optional representative hostname (must be complete)')
    parser.add_argument('--repetition', type=int, default=1, help='Representative repetition, default 1')
    args = parser.parse_args()
    out = args.output.resolve()
    path = out/'trials.csv'
    if not path.exists():
        parser.error(f'Not found: {path}')
    with path.open(newline='') as f:
        records = list(csv.DictReader(f))
    manifest = json.loads((out/'manifest.json').read_text())
    nrep = manifest['repetitions']
    if not 1 <= args.repetition <= nrep:
        parser.error(f'--repetition must be between 1 and {nrep}')
    by_dest = defaultdict(dict)
    for r in records:
        key = (r['host'], r['port'])
        by_dest[key][(int(r['repetition']),r['requested_algorithm'])] = r
    expected = {(rep, a) for rep in range(1, nrep+1) for a in ALGORITHMS}
    complete = {dest: m for dest, m in by_dest.items()
                if expected.issubset(m) and all(m[x]['status']=='ok' for x in expected)}
    if not complete:
        print('No destination has all four algorithms across all repetitions; no comparison generated.')
        return 2
    if args.destination:
        matches = [x for x in complete if x[0] == args.destination]
        if not matches:
            parser.error('Requested representative hostname is missing complete trials')
        rep_dest = matches[0]
    else:
        rep_dest = next(iter(complete))

    agg = []
    for dest, trials in complete.items():
        for algo in ALGORITHMS:
            mine = [trials[(i,algo)] for i in range(1,nrep+1)]
            good = [float(x['mean_mbps']) for x in mine]
            rtt = [float(x['mean_rtt_ms']) for x in mine if x['mean_rtt_ms']]
            agg.append(dict(host=dest[0], port=dest[1], algorithm=algo, repetitions=nrep,
                            mean_goodput_mbps=statistics.mean(good),
                            median_run_goodput_mbps=statistics.median(good),
                            stdev_run_goodput_mbps=statistics.stdev(good) if len(good)>1 else 0,
                            goodput_cv_pct=(100*statistics.stdev(good)/statistics.mean(good) if len(good)>1 and statistics.mean(good)>0 else 0),
                            min_run_goodput_mbps=min(good), max_run_goodput_mbps=max(good),
                            mean_rtt_ms=statistics.mean(rtt) if rtt else '',
                            median_run_rtt_ms=statistics.median(rtt) if rtt else '',
                            stdev_run_rtt_ms=statistics.stdev(rtt) if len(rtt)>1 else (0 if rtt else ''),
                            mean_retransmissions_per_run=statistics.mean(int(x['retransmissions']) for x in mine),
                            total_retransmissions=sum(int(x['retransmissions']) for x in mine)))
    with (out/'aggregate.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(agg[0]))
        writer.writeheader()
        writer.writerows(agg)

    # A single representative repetition is used for the 8 comparable plots;
    # other repetitions contribute to aggregates, not joined time axes.
    data = {}
    for algo in ALGORITHMS:
        r = complete[rep_dest][(args.repetition,algo)]
        trace = out/f'run_{args.repetition:02d}'/algo/f"{r['run_id']}_samples.csv"
        if not trace.is_file():
            parser.error(f'Missing raw samples: {trace}')
        data[algo] = _load_csv(trace)
        if not data[algo]:
            parser.error(f'Empty raw samples: {trace}')

    allruns = list(data.values())
    allc = [v for rows in allruns for v in _col(rows, 'snd_cwnd_segments')]
    allr = [v/1000 for rows in allruns for v in _col(rows,'rtt_us')]
    allrv = [v/1000 for rows in allruns for v in _col(rows,'rttvar_us')]
    allg = [v for rows in allruns for v in _col(rows,'goodput_mbps')]
    alll = [v for rows in allruns for v in _col(rows,_loss_key(rows))]
    maxvalues = dict(snd_cwnd_segments=max(allc,default=0),
                     rtt_ms=max(allr+allrv,default=0),
                     goodput_mbps=max(allg,default=0),
                     loss_proxy=max(alll,default=0))
    xlimits = dict(snd_cwnd_segments=maxvalues['snd_cwnd_segments'],
                   rtt_ms=max(allr,default=0),loss_proxy=maxvalues['loss_proxy'])
    xend = max(max(_col(rows,'elapsed_s')) for rows in allruns)
    pdfpath = out/'comparison.pdf'
    with PdfPages(pdfpath) as pdf:
        for algo in ALGORITHMS:
            title = f'{algo.upper()} | {rep_dest[0]}:{rep_dest[1]} | repetition {args.repetition}'
            _time_series_page(data[algo], title, xlim=(0,xend), ylims=maxvalues)
            pdf.savefig(plt.gcf()); plt.close('all')
            _scatter_page(data[algo], title, xlims=xlimits, ylims=maxvalues)
            pdf.savefig(plt.gcf()); plt.close('all')

        # Supplementary, independently scaled RLA pages. Do not substitute
        # these for the common-scale comparisons above.
        zoom_title = (f'RLA DETAIL (individual scale; not cross-algorithm comparable) | '
                      f'{rep_dest[0]}:{rep_dest[1]} | repetition {args.repetition}')
        _time_series_page(data['rla'], zoom_title, xlim=(0,xend))
        pdf.savefig(plt.gcf()); plt.close('all')
        _scatter_page(data['rla'], zoom_title)
        pdf.savefig(plt.gcf()); plt.close('all')

    print(f'Complete destinations: {len(complete)} / {len(by_dest)}')
    print(f'Representative: {rep_dest[0]}:{rep_dest[1]}')
    print(f'Wrote {out/"aggregate.csv"} and {pdfpath}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
