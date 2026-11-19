# Hot-key contention in rate-limited access control on Hyperledger Fabric

Code, raw data and analysis for the paper:

> F. Khalil, S. Abdelgaber, E. Shaaban, "Hot-Key Contention in Rate-Limited Access Control on Permissioned Blockchains: A Block-Occupancy Model and the Commitâ€“Accuracy Trade-off" (manuscript under preparation).

A per-user request counter, as used to rate-limit break-glass (emergency) access to electronic health records, becomes a hot key on an execute-order-validate blockchain: concurrent requests read the same version and all but one per block fail with `MVCC_READ_CONFLICT`. This repository holds the chaincode with six counter designs, the Caliper workloads, the raw logs of all 1,500 benchmark rounds (876,000 client calls, 20 trials per configuration), and the scripts that rebuild every table and figure of the paper.

## Repository layout

```
chaincode/bgac-contention/   Go chaincode for Fabric 1.4 (six counter designs) + unit tests
caliper/                     Caliper 0.5 workload (contention.js) and benchmark configs E1â€“E5
scripts/                     deploy, run and export scripts; analysis (analyze, model, accuracy)
analysis/                    rounds.py, figure scripts (figs.py, fig6.py)
data/raw/caliper-logs/       Caliper console logs, one per experiment part (gzip)
data/raw/caliper-reports/    Caliper HTML reports that were kept (E1bâ€“E1d)
data/raw/ledger-logs/E4|E5/  committed request logs exported from the ledger, one JSON per round
data/processed/              rounds.csv, per-configuration cells, model fit, accuracy tables
figures/                     Figures 1â€“6 as in the manuscript (PNG 300 dpi + PDF)
reproduce.sh                 rebuilds data/processed and figures from data/raw
```

## Counter designs

| Design (`strategy`) | Reads | Writes | Admission rule |
|---|---|---|---|
| `single` | the actor's counter key | the same key | exact |
| `part` | one partition (hash of tx ID) | the same partition | partition count < âŒŠL/NâŒ‹ (approximate) |
| `partceil` | one partition | the same partition | partition count < âŒˆL/NâŒ‰ (approximate) |
| `partsum` | all N partitions | own partition | sum < L (exact) |
| `deltarange` | range of the actor's delta keys | one new delta key | range count < L (exact) |
| `deltawrite` | the actor's BLOCK flag only | one new delta key | not blocked (deferred) |

`deltawrite` with an off-chain monitor (`deltackpt` in E5) counts the delta keys with a read-only query every K calls and submits a `block` transaction once the count reaches L.

## Experiments

Round label: `<exp>-<strategy>-p<N>-a<actors>-L<limit>-<load>tps-t<trial>` (limit 1000000 = no limit, pure contention).

| Exp | Question | Varies | Rounds |
|---|---|---|---|
| E1 | goodput of each design | 5 designs Ã— load 5/10/20/50/100 tx/s | 500 |
| E2 | partitions | N = 1â€¦64 Ã— load 5/20/50 tx/s | 420 |
| E3 | actors | 1/3/10 actors Ã— single/part/deltawrite Ã— load 20/50 tx/s | 360 |
| E4 | enforcement accuracy | 7 design/N settings, 200 requests at 20 tx/s, limit 50 | 140 |
| E5 | deferred enforcement | monitor every K = none/20/40/100 calls, limit 50 | 80 |

Ledger growth filled the VM disk, so E1 was run in four parts (trials 1â€“7, 8â€“14, 15â€“17, 18â€“20; logs `E1a`â€“`E1d`) and E3 in two (trials 1â€“10, 11â€“20), with the network rebuilt between parts. The labels keep the global trial number, so the analysis merges the parts. The E4 log and ledger export carry the run ID `pilot`; they are the full 20-trial E4 run used in the paper.

A round is **degraded** when Caliper's achieved send rate fell below 90% of the offered load (a client or VM stall). `cells_all.csv` keeps every round; `cells_clean.csv` excludes degraded rounds. Both are reported.

## Reproducing the analysis

Needs Python 3 with numpy, pandas, scipy and matplotlib (`pip install -r requirements.txt`).

```bash
./reproduce.sh
```

It decompresses the logs into `build/`, and writes `build/processed/` and `build/figures/`, which should match `data/processed/` and `figures/`. The block-occupancy model alone:

```bash
python3 scripts/model.py data/processed/cells_clean.csv
```

## Re-running the experiments

Testbed used in the paper: Hyperledger Fabric 1.4.12 in Docker on one Ubuntu VM (3 vCPUs, 7.3 GB RAM); two organisations with two peers each; one solo orderer with `MaxMessageCount 10` and `BatchTimeout 2s`; goleveldb state database; channel `appchannel`; endorsement policy `OR('HospitalMSP1.member','HospitalMSP2.member')`. Caliper 0.5.0 on Node.js 16 with one worker, fixed-rate control, all requests endorsed by `peer0.hospital1.com`.

1. Check `scripts/env.sh` against your network (CLI container, orderer, MSP IDs, policy).
2. `scripts/deploy.sh` installs and instantiates `bgac-contention`. Fabric 1.4 reuses a chaincode image by name and version, so the script removes old `dev-*bgac-contention*` images first.
3. Generate the benchmark configs, e.g. `python3 scripts/gen_configs.py --trials 20`, or split one experiment: `python3 scripts/gen_configs.py --trials 20 --only E3 --range 1-10 --suffix a`.
4. Run: `CALIPER_WS=<folder with Caliper installed> RUN_ID=r1 scripts/run_experiment.sh E1`.
5. For E4/E5, export the committed logs: `RUN_ID=r1 scripts/export_logs.sh E4`, then `python3 scripts/accuracy.py results/logs-E4-r1/*.json`.

The ledger stores failed transactions too, so watch the disk and rebuild the network between long parts.

Unit tests (logic only; `MockStub` runs transactions serially, so it shows no MVCC conflicts) need the Fabric v1.4.12 source in `GOPATH` with `GO111MODULE=off`: place `contention*.go` under `$GOPATH/src/github.com/hyperledger/fabric/examples/bgac` and run `go test -v .`.

## License

Code: MIT (see `LICENSE`). Data in `data/` and figures: CC BY 4.0.

## Contact

<<<<<<< HEAD
Fahima Khalil â€” f.khalil@bsu.edu.eg
=======
Fahima Khalil — engfahimakhalil@gmail.com
>>>>>>> 9d66bdd7dd343d295a79d65551625c1814a7a159
