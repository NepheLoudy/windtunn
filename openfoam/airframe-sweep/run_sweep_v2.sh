#!/usr/bin/env bash
# 扫气引擎 v2: 网格复用 (同一 (alpha,beta,delta) 几何组的 V 扫描只建一次网格)
#   usage: SWEEP_V="15 20 25 30" SWEEP_ALPHA="..." SWEEP_BETA="..." \
#          ./run_sweep_v2.sh <work_root> [nproc]
#
# 断点续传: case 的 results.json 存在则跳过; 网格缓存: 首个 V 建网格, 其余 clone_case。
# endTime 按 |alpha| 分档: <=5° -> 600 | 7.5~12.5° -> 1000 | 15° -> 1500
set -euo pipefail

ROOT=${1:?usage: SWEEP_V=... SWEEP_ALPHA=... SWEEP_BETA=... ./run_sweep_v2.sh <root> [nproc]}
NP=${2:-8}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT_CSV=${OUT_CSV:-"$HERE/../../guidance_sim/aero/aero_table.csv"}
SWEEP_V=${SWEEP_V:-"15 20 25 30"}
SWEEP_ALPHA=${SWEEP_ALPHA:-"-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"}
SWEEP_BETA=${SWEEP_BETA:-"0"}
GEOM=${GEOM_DIR:-"$HERE/cfd_geom_multi"}
SURF_LEVEL=${SURF_LEVEL:-5}
FIN_LEVEL=${FIN_LEVEL:-7}
BOX_LEVEL=${BOX_LEVEL:-3}
mkdir -p "$ROOT"

set +u
set +e
source /opt/openfoam12/etc/bashrc
set -eu

n_done=0; n_run=0
# 多机安全: 启动时读结果表建已完工况集合 (同表并行扫气自动去重跳过)
declare -A DONE_SET
if [ -f "$OUT_CSV" ]; then
  while IFS=, read -r V A B DE DA DR REST; do
    case "$V" in ''|'#'*) continue;; esac
    DONE_SET["V${V%.*}_a${A%.*}_b${B%.*}"]=1
    DONE_SET["V${V%.*}_a${A}_b${B}"]=1
  done < "$OUT_CSV"
  echo "表判重集: ${#DONE_SET[@]} 键"
fi
for A in $SWEEP_ALPHA; do
  for B in $SWEEP_BETA; do
    group_src=""
    for V in $SWEEP_V; do
      tag="V${V}_a${A}_b${B}"
      CASE="$ROOT/case_$tag"
      n_run=$((n_run+1))
      if [ -f "$CASE/results.json" ]; then
        echo "[$n_run] $tag — 已完成, 跳过"; n_done=$((n_done+1)); continue
      fi
      if [ -n "${DONE_SET[$tag]:-}" ]; then
        echo "[$n_run] $tag — 表中已有(其他机器完成), 跳过"; n_done=$((n_done+1)); continue
      fi
      echo "===== [$n_run] $tag ====="
      if [ -z "$group_src" ]; then
        rm -rf "$CASE"
        SURF_LEVEL=$SURF_LEVEL FIN_LEVEL=$FIN_LEVEL BOX_LEVEL=$BOX_LEVEL \
          GEOM_DIR="$GEOM" "$HERE/make_case.sh" "$V" "$A" "$B" "$CASE" > /dev/null
        echo "  meshing (blockMesh+snappy)..."
        ( cd "$CASE" && blockMesh > log.blockMesh 2>&1 && snappyHexMesh -overwrite > log.snappy 2>&1 ) || {
          echo "  MESH FAILED — $CASE/log.snappy"; continue; }
        group_src="$CASE"
      else
        "$HERE/clone_case.sh" "$group_src" "$CASE" "$V"
      fi
      ET=600
      ia=$(awk -v a="$A" 'BEGIN{print (a<0?-a:a)}')
      if awk -v a="$ia" 'BEGIN{exit !(a>6.7)}'; then ET=1000; fi
      if awk -v a="$ia" 'BEGIN{exit !(a>13.7)}'; then ET=1500; fi
      "$HERE/run_solve.sh" "$CASE" "$NP" "$ET" > "$ROOT/log.$tag" 2>&1 || {
        echo "  RUN FAILED — $ROOT/log.$tag"; continue; }
      python3 "$HERE/post_process.py" "$CASE" \
              --mass-props "$HERE/cad/v1/cfd/mass_properties.json" \
              --json "$CASE/results.json" --out "$OUT_CSV" || { echo "  POST FAILED"; continue; }
      n_done=$((n_done+1))
    done
  done
done
echo "=== 扫气完成: $n_done/$n_run -> $OUT_CSV ==="
"$HERE/notify_done.sh" "扫气批次完成" "$n_done/$n_run 工况完成 -> $OUT_CSV (anchor/全表批次)"
