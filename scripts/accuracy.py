#!/usr/bin/env python3
"""Enforcement accuracy (E4/E5) from exported ledger logs.

Input: one JSON file per round, produced by export_logs.sh (the chaincode's
exportLog output: every COMMITTED request of that round). Uncommitted
(MVCC-failed) requests left no log, so they are neither admitted nor denied.

Per round (single actor, limit L from the round label):
  committed    = committed requests
  admitted     = committed requests with allowed=true
  Reference = an ideal exact enforcer that admits the FIRST L committed
  requests and denies the rest (order = proposal timestamp, an
  approximation of commit order with one Caliper worker).
  over         = requests admitted at position >= L   (wrongly admitted)
  early_denied = requests denied at position < L      (wrongly denied)
Usage: python3 -I accuracy.py logs_dir/*.json [--csv acc.csv]
"""
import json, re, sys, os, math, csv
from collections import defaultdict

LBL = re.compile(r'(E\d)-([a-z]+)-p(\d+)-a(\d+)-L(\d+)-(\d+)tps-t(\d+)')
T95 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,9:2.262,10:2.228,
       14:2.145,19:2.093}

def ci(v):
    n = len(v); m = sum(v)/n if n else float('nan')
    if n < 2: return n, m, float('nan')
    sd = math.sqrt(sum((x-m)**2 for x in v)/(n-1)); return n, m, T95.get(n-1, 1.96)*sd/math.sqrt(n)

def main():
    argv = sys.argv[1:]; out = None
    if '--csv' in argv:
        i = argv.index('--csv'); out = argv[i+1]; del argv[i:i+2]
    if not argv: sys.exit(__doc__)
    cells = defaultdict(list)
    for p in argv:
        m = LBL.search(os.path.basename(p))
        if not m: print('skip (no label):', p); continue
        exp, s, n, a, L, load, t = m.groups(); L = int(L)
        entries = sorted(json.load(open(p)), key=lambda e: e['tsNanos'])
        admitted = sum(1 for e in entries if e['allowed'])
        over = sum(1 for i, e in enumerate(entries) if e['allowed'] and i >= L)
        early = sum(1 for i, e in enumerate(entries) if not e['allowed'] and i < L)
        cells[(exp, s, int(n), L)].append(dict(committed=len(entries), admitted=admitted,
                                               over=over, early=early))
    rows = []
    print(f"{'exp':<4}{'strategy':<11}{'N':>3}{'L':>5}{'n':>4}{'committed':>18}{'admitted':>18}{'over-admit':>16}{'early-deny':>16}")
    for k in sorted(cells):
        rs = cells[k]; f = lambda key: ci([r[key] for r in rs])
        c, ad, ov, ed = f('committed'), f('admitted'), f('over'), f('early')
        print(f"{k[0]:<4}{k[1]:<11}{k[2]:>3}{k[3]:>5}{c[0]:>4}" + ''.join(f"{x[1]:>9.1f} +/- {x[2]:<5.1f}" for x in (c, ad, ov, ed)))
        rows.append(dict(exp=k[0], strategy=k[1], partitions=k[2], limit=k[3], trials=c[0],
                         committed=round(c[1],2), admitted=round(ad[1],2), admitted_ci95=round(ad[2],2),
                         over_admit=round(ov[1],2), early_deny=round(ed[1],2)))
    if out and rows:
        with open(out, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

if __name__ == '__main__':
    main()
