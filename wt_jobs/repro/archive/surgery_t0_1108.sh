#!/usr/bin/env bash
# 11-08 手术: 11-05 01:41 内联启动缺 OUT_CSV → 168+44 行落错表 (aero_table.csv 默认路径)
# 判重集启动时冻结 → 本 runner 必然再浪费 ~158 例旧网格重跑 (≈2.7 天)。
# 处置: 杀 chain (防 T1 抢跑) → 杀 runner 树 → 清无 results.json 残骸 →
#       recover_table 回填 168 行 → 全 env 重启 (扩格 20-25 目标网格) → chain 自愈恢复。
set -x
date
# 1) 备份搁浅表 (44 行重跑对照数据只此一份)
cp -n "$HOME/windtunnel/guidance_sim/aero/aero_table.csv" \
      "$HOME/windtunnel/guidance_sim/aero/aero_table_stranded_1108.csv"
# 2) 杀 chain (防 T1 抢跑)
pkill -f 'chain_t1_v[3]'; sleep 1
# 3) 杀 runner 树
pkill -f 'run_sweep_v[2]'
pkill -f 'run_solve[.]sh'
pkill -f 'mpirun.*iface l[o]'
sleep 3
echo "== survivors:"
pgrep -af 'run_sweep|run_solve|mpirun|foamRun|chain_t1' | grep -v grep || echo none
# 4) 清理无 results.json 的残骸 case (断电铁律: 不完整=垃圾)
for d in "$HOME"/sweep_t0v2/case_*; do
  [ -d "$d" ] || continue
  [ -f "$d/results.json" ] || rm -rf "$d"
done
echo "== cases left: $(ls -d "$HOME"/sweep_t0v2/case_* 2>/dev/null | wc -l)"
# 5) 回填 168 行 (幂等: 表判重按 V/alpha/beta)
python3 "$HOME/recover_table.py" 2>&1 | tail -4
echo "== t0_table rows: $(wc -l < "$HOME/sweep_t0v2/t0_table.csv")"
# 6) 全 env 重启 (扩格目标网格 V20-25)
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
pgrep -cf 'run_sweep_v[2]' >/dev/null && echo RUNNER_ALIVE || echo RUNNER_DEAD
# 7) chain 自愈恢复 (guard 兜底, 这里立即拉齐)
setsid nohup bash "$HOME/chain_t1_v3.sh" >> "$HOME/chain_v3.log" 2>&1 < /dev/null &
sleep 1
pgrep -cf 'chain_t1_v[3]' >/dev/null && echo CHAIN_ALIVE || echo CHAIN_DEAD
date
