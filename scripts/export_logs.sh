#!/usr/bin/env bash
# Usage: RUN_ID=r1 ./export_logs.sh E4
# Exports the committed log of every round of an experiment to ../results/logs-<EXP>-<RUN_ID>/<label>.json
set -euo pipefail
EXP=${1:?experiment id}; : "${RUN_ID:?set RUN_ID}"
cd "$(dirname "$0")"; source ./env.sh
OUT=../results/logs-$EXP-$RUN_ID; mkdir -p "$OUT"
for lbl in $(grep -oE "label: E[0-9]+-[^ ]+" ../caliper/benchmark-$EXP.yaml | cut -d' ' -f2); do
  docker exec $CLI bash -c "$ORG1_ENV peer chaincode query -C $CHANNEL -n $CC_NAME -c '{\"Args\":[\"exportLog\",\"$RUN_ID-$lbl\"]}'" > "$OUT/$lbl.json"
  echo "$lbl: $(/usr/bin/python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$OUT/$lbl.json") entries"
done
