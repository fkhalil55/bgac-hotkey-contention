#!/usr/bin/env python3
"""Generate Caliper 0.5 benchmark configs for experiments E1-E5.

Round label format (parsed by analyze.py):
    <exp>-<strategy>-p<N>-a<actors>-L<limit>-<load>tps-t<trial>
Usage:  python3 gen_configs.py [--trials 20] [--secs 20] [--out ../caliper]
        python3 gen_configs.py --only E3 --range 1-10 --suffix a   -> benchmark-E3a.yaml
Splitting an experiment into trial ranges lets the network be reset between
parts (the ledger stores every transaction, including failed ones, and fills
the VM disk). Labels stay E3-...-t<k>, so analyze.py merges the parts' logs.
"""
import argparse, os

UNLIMITED = 1_000_000  # limit so high that nothing is denied: pure contention
PEER1 = ["peer0.hospital1.com"]

def experiments(trials):
    E = {}
    # E1 strategy comparison, 1 actor, no denials
    E["E1"] = [(s, n, 1, UNLIMITED, load)
               for load in (5, 10, 20, 50, 100)
               for s, n in (("single", 1), ("part", 16), ("partsum", 16),
                            ("deltarange", 1), ("deltawrite", 1))]
    # E2 partition sweep
    E["E2"] = [("part", n, 1, UNLIMITED, load)
               for load in (5, 20, 50) for n in (1, 2, 4, 8, 16, 32, 64)]
    # E3 actor sweep
    E["E3"] = [(s, n, a, UNLIMITED, load)
               for load in (20, 50) for a in (1, 3, 10)
               for s, n in (("single", 1), ("part", 16), ("deltawrite", 1))]
    # E4 enforcement accuracy: limit 50, 200 requests per round (txNumber fixed below)
    E["E4"] = [(s, n, 1, 50, 20)
               for s, n in (("single", 1), ("part", 4), ("part", 16), ("part", 32),
                            ("partceil", 16), ("partsum", 16), ("deltarange", 1))]
    # E5 deferred enforcement: write-only deltas + off-chain monitor that checks
    # the count every K calls (p<K> in the label; K=0 = no monitor). limit 50.
    E["E5"] = [("deltackpt", k, 1, 50, 20) for k in (0, 20, 40, 100)]
    return E

def round_yaml(exp, s, n, a, limit, load, t, secs):
    tag = f"{exp}-{s}-p{n}-a{a}-L{limit}-{load}tps-t{t}"
    tx = 200 if exp in ("E4", "E5") else load * secs
    return f"""  - label: {tag}
    txNumber: {tx}
    rateControl:
      type: fixed-rate
      opts:
        tps: {load}
    workload:
      module: caliper/benchmarks/callbacks/contention.js
      arguments:
        strategy: {s}
        partitions: {n}
        actors: {a}
        limit: {limit}
        bucketSecs: 0
        tag: {tag}
        targetPeers: {PEER1}
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--secs", type=int, default=20, help="seconds per round for E1-E3")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "caliper"))
    ap.add_argument("--only", help="generate only this experiment, e.g. E3")
    ap.add_argument("--range", help="trial range, e.g. 1-10 (default: all trials)")
    ap.add_argument("--suffix", default="", help="file suffix, e.g. a -> benchmark-E3a.yaml")
    o = ap.parse_args()
    lo, hi = (map(int, o.range.split("-")) if o.range else (1, o.trials))
    for exp, cells in experiments(o.trials).items():
        if o.only and exp != o.only:
            continue
        rounds = [round_yaml(exp, *c, t, o.secs) for t in range(lo, hi + 1) for c in cells]
        path = os.path.join(o.out, f"benchmark-{exp}{o.suffix}.yaml")
        with open(path, "w") as f:
            f.write(f"test:\n  name: bgac-contention-{exp}\n  workers:\n    number: 1\n  rounds:\n")
            f.write("".join(rounds))
        tx = sum(int(r.split("txNumber: ")[1].split()[0]) for r in rounds)
        print(f"{path}: {len(cells)} configs x trials {lo}-{hi} = {len(rounds)} rounds, {tx:,} tx")

if __name__ == "__main__":
    main()
