#!/usr/bin/env bash
# Rebuild every table and figure of the paper from the raw logs in data/raw.
# Needs: python3 with numpy, pandas, scipy, matplotlib (pip install -r requirements.txt)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
B=build; rm -rf "$B"; mkdir -p "$B/logs" "$B/processed" "$B/figures"

for f in data/raw/caliper-logs/*.log.gz; do gunzip -c "$f" > "$B/logs/$(basename "${f%.gz}")"; done

# one row per round (1,500 rounds)
$PY analysis/rounds.py "$B/logs" "$B/processed/rounds.csv"

# per-configuration cells: all rounds and degraded rounds excluded
$PY scripts/analyze.py "$B"/logs/caliper-*.log --csv "$B/processed/cells_all.csv"  > "$B/processed/cells_all.txt"
$PY scripts/analyze.py "$B"/logs/caliper-*.log --exclude-degraded --csv "$B/processed/cells_clean.csv" > "$B/processed/cells_clean.txt"

# block-occupancy model vs measurement
$PY scripts/model.py "$B/processed/cells_clean.csv" > "$B/processed/model_clean.txt"

# enforcement accuracy from the exported ledger logs (E4, E5)
$PY scripts/accuracy.py data/raw/ledger-logs/E4/*.json --csv "$B/processed/accuracy.csv"    > "$B/processed/accuracy.txt"
$PY scripts/accuracy.py data/raw/ledger-logs/E5/*.json --csv "$B/processed/accuracy_E5.csv" > "$B/processed/accuracy_E5.txt"

# figures (manuscript numbering)
$PY analysis/figs.py "$B/processed/rounds.csv" "$B/figures" "$B/processed/accuracy.csv"
$PY analysis/fig6.py "$B/processed/accuracy_E5.csv" "$B/figures"

echo "done: $B/processed and $B/figures (compare with data/processed and figures/)"
