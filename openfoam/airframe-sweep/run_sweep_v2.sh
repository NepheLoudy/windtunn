#!/usr/bin/env bash
# 扫气引擎 v2: 网格复用 (同一 (alpha,beta,delta) 几何组的 V 扫描只建一次网格)
#   usage: SWEEP_V="15 20 25 30" SWEEP_ALPHA="..." SWEEP_BETA="..." OUT_CSV=<表路径> \
#          ./run_sweep_v2.sh <work_root> [nproc]
#   SWEEP_V/SWEEP_ALPHA/SWEEP_BETA 缺失即 FATAL (E1 守卫); OUT_CSV 未显式时守卫不拦、
#   会落默认交付正本路径 — 直跑必须显式带 OUT_CSV; 正规入口 = sweep_packs/run_pack.sh 领包
#   其余 env: GEOM_DIR (默认 cad/v1/cfd_geom_multi_parallel 真源) / SURF_LEVEL=5 / FIN_LEVEL=7 / BOX_LEVEL=3
#
# 断点续传: case 的 results.json 存在则跳过; 网格缓存: 首个 V 建网格, 其余 clone_case。
# endTime 按 |alpha| 分档: <=5° -> 600 | 7.5~12.5° -> 1000 | 15° -> 1500
set -euo pipefail

ROOT=${1:?usage: SWEEP_V=... SWEEP_ALPHA=... SWEEP_BETA=... ./run_sweep_v2.sh <root> [nproc]}
NP=${2:-8}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT_CSV=${OUT_CSV:-"$HERE/../../guidance_sim/aero/aero_table.csv"}
# 缺省即报错 (E1, 2026-11-19 审查): 默认旧域会静默写错行; 走 run_pack.sh 领包才是正规入口
# ${OUT_CSV+x} 判"是否显式传入" (默认值会写交付正本, 必须显式)
if [ -z "${SWEEP_V:-}" ] || [ -z "${SWEEP_ALPHA:-}" ] || [ -z "${SWEEP_BETA:-}" ] || [ -z "${OUT_CSV+x}" ]; then
  echo "FATAL: 缺 env (SWEEP_V/SWEEP_ALPHA/SWEEP_BETA/OUT_CSV) — 请走 sweep_packs/run_pack.sh 领包, 不直接调本脚本" >&2
  exit 2
fi
SWEEP_V=${SWEEP_V}
SWEEP_ALPHA=${SWEEP_ALPHA}
SWEEP_BETA=${SWEEP_BETA}
GEOM=${GEOM_DIR:-"$HERE/cad/v1/cfd_geom_multi_parallel"}
SURF_LEVEL=${SURF_LEVEL:-5}
FIN_LEVEL=${FIN_LEVEL:-7}
BOX_LEVEL=${BOX_LEVEL:-3}
mkdir -p "$ROOT"

set +u
set +e
# OpenFOAM 环境自适应 (apt /opt → 源码编译 ~/OpenFOAM-12 → /usr/lib)
if [ -f /opt/openfoam12/etc/bashrc ]; then source /opt/openfoam12/etc/bashrc 2>/dev/null
elif [ -f "$HOME/OpenFOAM-12/etc/bashrc" ]; then source "$HOME/OpenFOAM-12/etc/bashrc" 2>/dev/null
elif [ -f /usr/lib/openfoam/openfoam12/etc/bashrc ]; then source /usr/lib/openfoam/openfoam12/etc/bashrc 2>/dev/null
fi
set -eu
# 无头机: MPI 的 hwloc_gl 插件 XOpenDisplay 会挂死
unset DISPLAY
export HWLOC_COMPONENTS=-gl

n_done=0; n_run=0; n_fail=0
# 多机安全: 启动时读结果表建已完工况集合 (同表并行扫气自动去重跳过)
# 键归一用 printf %g — ${B%.*} 对 β=±2.5 会截成 -2 与 tag b-2.5 失配 (2026-11-19 审查 B1)
declare -A DONE_SET
norm_key() { printf 'V%g_a%g_b%g' "$1" "$2" "$3"; }
if [ -f "$OUT_CSV" ]; then
  while IFS=, read -r V A B DE DA DR REST; do
    # 只吃数据行: 跳过注释/空行/列名行 (V 开头非数字) — 列名行喂 printf %g 会报错+set -e 炸脚本 (2026-11-19 07:00 值班)
    case "$V" in ''|'#'*) continue;; esac
    [[ "$V" =~ ^[0-9] ]] || continue
    DONE_SET[$(norm_key "$V" "$A" "$B")]=1
    DONE_SET["$(norm_key "${V%.*}" "${A%.*}" "${B%.*}")"]=1
  done < "$OUT_CSV"
  echo "表判重集: ${#DONE_SET[@]} 键"
fi
for A in $SWEEP_ALPHA; do
  for B in $SWEEP_BETA; do
    group_src=""
    warm_src=""     # 热启动场源: 组内最近一个「跑成功且收敛」的 case (空=冷启动)
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
        if ! SURF_LEVEL=$SURF_LEVEL FIN_LEVEL=$FIN_LEVEL BOX_LEVEL=$BOX_LEVEL \
          GEOM_DIR="$GEOM" "$HERE/make_case.sh" "$V" "$A" "$B" "$CASE" > /dev/null; then
          echo "  MAKE FAILED — $CASE (几何/模板问题)"; n_fail=$((n_fail+1)); continue
        fi
        echo "  meshing (blockMesh+snappy)..."
        ( cd "$CASE" && blockMesh > log.blockMesh 2>&1 && snappyHexMesh -overwrite > log.snappy 2>&1 ) || {
          echo "  MESH FAILED — $CASE/log.snappy"; n_fail=$((n_fail+1)); continue; }
        group_src="$CASE"
      else
        WARM_FROM="$warm_src" "$HERE/clone_case.sh" "$group_src" "$CASE" "$V"
      fi
      ET=600
      ia=$(awk -v a="$A" 'BEGIN{print (a<0?-a:a)}')
      if awk -v a="$ia" 'BEGIN{exit !(a>6.7)}'; then ET=1000; fi
      if awk -v a="$ia" 'BEGIN{exit !(a>13.7)}'; then ET=1500; fi
      "$HERE/run_solve.sh" "$CASE" "$NP" "$ET" > "$ROOT/log.$tag" 2>&1 || {
        echo "  RUN FAILED — $ROOT/log.$tag"; n_fail=$((n_fail+1)); continue; }
      python3 "$HERE/post_process.py" "$CASE" \
              --mass-props "$HERE/cad/v1/cfd/mass_properties.json" \
              --json "$CASE/results.json" --out "$OUT_CSV" || { echo "  POST FAILED"; n_fail=$((n_fail+1)); continue; }
      n_done=$((n_done+1))
      warm_src="$CASE"   # 成功+落表才作热启动源 (clone_case 内部还会再校 residual_rel)
    done
  done
done
# 横幅与通知诚实化: 有失败必须显式说 (A3, 2026-11-19 审查)
if [ "$n_fail" -gt 0 ]; then
  echo "=== 扫气完成(有失败 $n_fail 例): $n_done/$n_run -> $OUT_CSV ==="
  "$HERE/notify_done.sh" "扫气批次完成(有失败 $n_fail 例)" "$n_done/$n_run 工况完成, 失败 $n_fail -> $OUT_CSV"
  exit 1   # 失败计数非零退出 → run_pack 聚合 partial
fi
echo "=== 扫气完成: $n_done/$n_run -> $OUT_CSV ==="
"$HERE/notify_done.sh" "扫气批次完成" "$n_done/$n_run 工况完成 -> $OUT_CSV (anchor/全表批次)"
