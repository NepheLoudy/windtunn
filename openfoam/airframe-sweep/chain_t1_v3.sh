#!/usr/bin/env bash
# T1-v2 链式启动 v3 — 完成判据 + 补跑循环 (10-30 全量审查: 失败工况引擎一轮内不重试)
# 逻辑: 引擎退出后查表行数, <364 就重启引擎(断点续传只补缺) 至多 3 轮;
#       >=360 放行 T1 并为其拉起独立收割机; 3 轮后仍 <360 也放行 T1 但留警告。
set +u
source "$HOME/OpenFOAM-12/etc/bashrc" 2>/dev/null
unset DISPLAY; export HWLOC_COMPONENTS=-gl

ROOT0=$HOME/sweep_t0v2
LOG=$ROOT0/chain_v3.log
echo "chain v3 start $(date)" >> "$LOG"

rows() { wc -l < "$ROOT0/t0_table.csv" 2>/dev/null || echo 0; }

# 等 T0 引擎退出 (不预设它在跑)
while pgrep -f "run_sweep_v[2]" >/dev/null 2>&1; do sleep 600; done

round=0
while true; do
  n=$(rows)
  echo "round $round check: rows=$n $(date)" >> "$LOG"
  if [ "$n" -ge 364 ]; then break; fi
  if [ "$round" -lt 3 ]; then
    # 补跑一轮 (引擎只跑缺 results.json 的工况)
    cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
    export OUT_CSV="$ROOT0/t0_table.csv"
    export SWEEP_V="15 20 25 30"
    export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
    export SWEEP_BETA="-15 -10 -5 0 5 10 15"
    export SURF_LEVEL=5 FIN_LEVEL=7 BOX_LEVEL=3
    export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
    setsid nohup ./run_sweep_v2.sh "$ROOT0" 14 >> "$ROOT0/sweep.log" 2>&1 < /dev/null &
    echo "round $((round+1)) engine relaunched for $n/364" >> "$LOG"
    round=$((round+1))
    sleep 300
    while pgrep -f "run_sweep_v[2]" >/dev/null 2>&1; do sleep 600; done
  else
    echo "WARN: 3 rounds exhausted, rows=$n < 364 — 放行 T1, 缺口留给人工" >> "$LOG"
    break
  fi
done

n=$(rows)
echo "T0 final rows=$n — firing T1-v2 $(date)" >> "$LOG"
# 为 T1 拉起独立收割机 (T1 case 1.3G, 不收割必爆盘)
setsid nohup bash ~/case_reaper.sh "$HOME/sweep_t1" 600 > "$HOME/sweep_t1/reaper.log" 2>&1 < /dev/null &
mkdir -p "$HOME/sweep_t1"
cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export OUT_CSV="$HOME/sweep_t1/t1_table.csv"
export SWEEP_V="15 20 25 30"
export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
export SWEEP_BETA="-15 -10 -5 0 5 10 15"
export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
setsid nohup ./run_sweep_v2.sh "$HOME/sweep_t1" 14 >> "$HOME/sweep_t1/sweep.log" 2>&1 < /dev/null &
echo "T1-v2 launched $(date)" >> "$LOG"
