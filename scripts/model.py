#!/usr/bin/env python3
"""Block-occupancy contention model vs measurement.

Fabric validates a block's transactions in order: among transactions in the
same block that read-modify-write the same key, only the first commits.
With B requests per block spread uniformly over N counter keys, the expected
number of commits per block is the expected number of DISTINCT keys hit:
        E[commits/block] = N * (1 - (1 - 1/N)**B)
        predicted success = E[commits/block] / B
B comes from the orderer config: B = min(MaxMessageCount, load * BatchTimeout).
(This VM: MaxMessageCount 10, BatchTimeout 2 s -> B = 10 for every load >= 5.)
The model ignores conflicts ACROSS blocks (stale endorsement); a measured
value below the prediction indicates them. This is a model: label it so.

Usage: /usr/bin/python3 -I model.py cells.csv [--max-msg 10] [--timeout 2]
       (cells.csv from analyze.py --csv; uses strategies single/part/partceil, 1 actor)
"""
import csv, sys

def predict(n, b):
    return n * (1 - (1 - 1 / n) ** b) / b

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    mx, to = 10, 2.0
    if '--max-msg' in a: mx = int(a[a.index('--max-msg') + 1])
    if '--timeout' in a: to = float(a[a.index('--timeout') + 1])
    print(f"{'exp':<4}{'strategy':<10}{'N':>4}{'load':>6}{'B':>4}{'measured %':>12}{'model %':>10}{'diff pp':>9}")
    for r in csv.DictReader(open(a[0])):
        if r['strategy'] not in ('single', 'part', 'partceil') or r['actors'] != '1':
            continue
        n, load = int(r['partitions']), int(r['load'])
        b = max(1, min(mx, round(load * to)))
        m, p = float(r['success_mean']), 100 * predict(n, b)
        print(f"{r['exp']:<4}{r['strategy']:<10}{n:>4}{load:>6}{b:>4}{m:>12.1f}{p:>10.1f}{m - p:>9.1f}")

if __name__ == '__main__':
    main()
