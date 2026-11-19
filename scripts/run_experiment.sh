#!/usr/bin/env bash
# Usage (inside tmux, with Node 16 active):  RUN_ID=r1 ./run_experiment.sh E4
# CALIPER_WS = the project folder you ran the Array benchmarks from (it contains
# node_modules/ and caliper/networks/network-config.yaml).
set -euo pipefail
EXP=${1:?experiment id, e.g. E1}
: "${RUN_ID:?set RUN_ID, e.g. RUN_ID=r1}"
CALIPER_WS=${CALIPER_WS:?set CALIPER_WS, e.g. export CALIPER_WS=~/fabric-realty}
NETCFG=${NETCFG:-caliper/networks/network-config.yaml}
HERE="$(cd "$(dirname "$0")" && pwd)"
node --version | grep -q '^v16' || { echo "Node 16 required: run  nvm use 16"; exit 1; }
mkdir -p "$HERE/../results" "$CALIPER_WS/caliper/benchmarks/callbacks"
cp "$HERE/../caliper/contention.js" "$CALIPER_WS/caliper/benchmarks/callbacks/contention.js"
cp "$HERE/../caliper/benchmark-$EXP.yaml" "$CALIPER_WS/caliper/benchmarks/benchmark-$EXP.yaml"
cd "$CALIPER_WS"
export RUN_ID
./node_modules/.bin/caliper launch manager \
  --caliper-workspace . \
  --caliper-networkconfig "$NETCFG" \
  --caliper-benchconfig "caliper/benchmarks/benchmark-$EXP.yaml" \
  --caliper-flow-skip-start \
  --caliper-flow-skip-end \
  --caliper-report-path "$HERE/../results/report-$EXP-$RUN_ID.html" \
  2>&1 | tee "$HERE/../results/caliper-$EXP-$RUN_ID.log"
