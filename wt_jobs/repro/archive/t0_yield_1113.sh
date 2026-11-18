#!/usr/bin/env bash
# 11-13 T0 让位处置: T1 跑了 11.5h 零产出(38min/例尚在首例求解段)而 T0 缺 83 例
# 序列: 杀 T1 树(保留半成品 case, 断点续跑) → 清 T0 无 results 残骸(重建是标准流程) → T0 全 env 重启
set -x
date
# 1) 杀 T1 树 (runner/run_solve/mpirun/foamRun 指向 sweep_t1 的)
pkill -f 'sweep_t[1]'; sleep 2
pkill -f 'run_solve[.]sh'; sleep 1
pkill -f 'mpirun.*iface l[o]'; sleep 3
echo "== survivors:"; pgrep -af 'run_sweep|run_solve|mpirun|foamRun' | grep -v grep || echo none
# 2) T0 残骸: 只清无 results.json 的 case (半成品网格/求解, 引擎 rm -rf 重建是标准流程)
for d in "$HOME"/sweep_t0v2/case_*; do
  [ -d "$d" ] || continue
  [ -f "$d/results.json" ] || rm -rf "$d"
done
echo "== T0 cases left: $(ls -d "$HOME"/sweep_t0v2/case_* 2>/dev/null | wc -l)"
# 3) T0 全 env 重启 (判重只补缺 83 例)
set +u
source "$HOME/OpenFOAM-12/etc/bashrc" 2>/dev/null
unset DISPLAY; export HWLOC_COMPONENTS=-gl
cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export OUT_CSV="$HOME/sweep_t0v2/t0_table.csv"
export SWEEP_V="20 21 22 23 24 25"
export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
export SWEEP_BETA="-15 -10 -5 0 5 10 15"
export SURF_LEVEL=5 FIN_LEVEL=7 BOX_LEVEL=3
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
setsid nohup ./run_sweep_v2.sh "$HOME/sweep_t0v2" 14 >> "$HOME/sweep_t0v2/sweep.log" 2>&1 < /dev/null &
sleep 3
pgrep -cf 'run_sweep_v[2]' >/dev/null && echo T0_RUNNER_ALIVE || echo T0_RUNNER_DEAD
date
