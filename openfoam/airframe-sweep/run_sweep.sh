#!/usr/bin/env bash
# 全表扫气: V × alpha × beta 网格 (de/da/dr=0, 舵偏扫气见 --deflect)
#   usage: SWEEP_V="15 20 25 30" SWEEP_ALPHA="-5 0 5 10 15" SWEEP_BETA="0" \
#          ./run_sweep.sh <work_root> [nproc]
# 断点可续: 已有 results.json 的工况跳过
set -euo pipefail

ROOT=${1:?usage: SWEEP_V=... SWEEP_ALPHA=... ./run_sweep.sh <work_root> [nproc]"}
NP=${2:-12}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT_CSV=${OUT_CSV:-"$HERE/../../guidance_sim/aero/aero_table.csv"}
SWEEP_V=${SWEEP_V:-"15 20 25 30"}
SWEEP_ALPHA=${SWEEP_ALPHA:-"-5 0 5 10 15"}
SWEEP_BETA=${SWEEP_BETA:-"0"}
mkdir -p "$ROOT"

set +u
source /opt/openfoam12/etc/bashrc
set -u

n=0
for V in $SWEEP_V; do
  for A in $SWEEP_ALPHA; do
    for B in $SWEEP_BETA; do
      tag="V${V}_a${A}_b${B}"
      CASE="$ROOT/case_$tag"
      n=$((n+1))
      if [ -f "$CASE/results.json" ]; then
        echo "[$n] $tag — 已完成, 跳过"
        continue
      fi
      echo "===== [$n] $tag ====="
      rm -rf "$CASE"
      "$HERE/make_case.sh" "$V" "$A" "$B" "$CASE" >/dev/null
      "$HERE/run_case.sh"   "$CASE" "$NP" > "$ROOT/log.$tag" 2>&1 || {
        echo "  RUN FAILED — 见 $ROOT/log.$tag"; continue; }
      python3 "$HERE/post_process.py" "$CASE" --json "$CASE/results.json" \
              --out "$OUT_CSV" || { echo "  POST FAILED"; continue; }
    done
  done
done
echo "=== 扫气完成: $(grep -c '^[0-9]' "$OUT_CSV" 2>/dev/null || echo 0) 行 -> $OUT_CSV ==="
