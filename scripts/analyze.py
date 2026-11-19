#!/usr/bin/env python3
"""Summarize contention experiments from Caliper console logs.

Round labels:  <exp>-<strategy>-p<N>-a<actors>-L<limit>-<load>tps-t<trial>
For every (exp, strategy, N, actors, limit, load) cell prints n, commit success
rate (per-trial mean +/- 95% t-CI), goodput (successful tx/s), throughput as
Caliper reports it (includes failures!) and mean latency.

Usage: /usr/bin/python3 -I analyze.py LOG [LOG ...] [--csv cells.csv] [--exclude-degraded]

A round is DEGRADED when Caliper's send rate fell below 90% of the offered
load (client/VM stall, not a property of the strategy). They are counted per
cell; --exclude-degraded drops them from the statistics (report both).
"""
import re, sys, math, csv
from collections import defaultdict

T95 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,9:2.262,10:2.228,
       11:2.201,12:2.179,13:2.160,14:2.145,15:2.131,16:2.120,17:2.110,18:2.101,19:2.093,
       20:2.086,24:2.064,29:2.045}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
ROW = re.compile(r'^\|\s*(E\d)-([a-z]+)-p(\d+)-a(\d+)-L(\d+)-(\d+)tps-t(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|'
                 r'\s*([\d.]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.\-]+)\s*\|\s*([\d.]+)\s*\|')

def num(s):
    try: return float(s)
    except ValueError: return None

def ci(vals):
    n = len(vals)
    if not n: return (0, float('nan'), float('nan'))
    m = sum(vals)/n
    if n == 1: return (1, m, float('nan'))
    sd = math.sqrt(sum((v-m)**2 for v in vals)/(n-1))
    return (n, m, T95.get(n-1, 1.96)*sd/math.sqrt(n))

def main():
    argv = sys.argv[1:]
    out = None
    if '--csv' in argv:
        i = argv.index('--csv'); out = argv[i+1]; del argv[i:i+2]
    excl = '--exclude-degraded' in argv
    argv = [a for a in argv if a != '--exclude-degraded']
    if not argv: sys.exit(__doc__)
    rounds = {}
    for p in argv:
        for line in open(p, errors='replace'):
            m = ROW.match(ANSI.sub('', line).strip())
            if not m: continue
            exp, s, n, a, L, load, t, succ, fail, send, mx, mn, avg, thr = m.groups()
            rounds[(exp, s, int(n), int(a), int(L), int(load), int(t))] = dict(
                succ=int(succ), fail=int(fail), avg=num(avg), thr=num(thr), send=num(send))
    cells = defaultdict(list); degraded = defaultdict(int)
    for k, r in rounds.items():
        bad = r['send'] is not None and r['send'] < 0.9 * k[5]
        if bad: degraded[k[:6]] += 1
        if bad and excl: continue
        cells[k[:6]].append(r)
    hdr = f"{'exp':<4}{'strategy':<11}{'N':>3}{'act':>4}{'load':>5}{'n':>4}  {'success %':>15}  {'goodput tx/s':>15}  {'caliper TPS':>11}  {'latency s':>9}{'degraded':>9}"
    print(f"{len(rounds)} rounds parsed; degraded rounds {'EXCLUDED' if excl else 'included'}\n"); print(hdr); print('-'*len(hdr))
    rows = []
    for k in sorted(cells):
        rs = cells[k]; exp, s, n, a, L, load = k
        sr = ci([100*r['succ']/(r['succ']+r['fail']) for r in rs if r['succ']+r['fail']])
        gp = ci([r['send']*r['succ']/(r['succ']+r['fail']) for r in rs if r['succ']+r['fail'] and r['send']])
        th = ci([r['thr'] for r in rs])
        lat = ci([r['avg'] for r in rs if r['avg'] is not None])
        print(f"{exp:<4}{s:<11}{n:>3}{a:>4}{load:>5}{sr[0]:>4}  {sr[1]:>7.1f} +/- {sr[2]:<4.1f}  {gp[1]:>7.2f} +/- {gp[2]:<4.2f}  {th[1]:>11.2f}  {lat[1]:>9.3f}{degraded[k]:>9}")
        rows.append(dict(exp=exp, strategy=s, partitions=n, actors=a, limit=L, load=load, trials=sr[0],
                         success_mean=round(sr[1],2), success_ci95=round(sr[2],2),
                         goodput_mean=round(gp[1],3), goodput_ci95=round(gp[2],3),
                         caliper_tps=round(th[1],3), latency_s=round(lat[1],4), degraded_rounds=degraded[k], degraded_excluded=excl))
    if out and rows:
        with open(out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        print(f"\nwrote {out}")

if __name__ == '__main__':
    main()
