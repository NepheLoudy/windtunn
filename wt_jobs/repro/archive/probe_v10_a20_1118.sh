#!/usr/bin/env bash
# 双探针: ①V10 量级(GPU LBM 300k) ②V15_a20_b0 大攻角定常可行性(CPU OpenFOAM 单例)
# ① GPU: V_LBM=0.05*10/20=0.025, NU=0.02*20/10=0.04 (Re 一致口径∝V/nu... 修正: NU∝1/V → NU=0.02*20/10=0.04 ✓)
cd ~/fluidx3d_v3/FluidX3D-master/bin
GEOM_DIR=cfd_v4parts/ ALPHA=0 BETA=0 NX=440 V_LBM=0.025 NU=0.04 STEPS=300000 TAG=_v10_probe \
  setsid nohup ./FluidX3D > v10_probe.log 2>&1 < /dev/null &
echo "GPU probe launched"

# ② CPU: V15_a20_b0 大攻角先导 (深失速定常可行性探路石)
set +u
source "$HOME/OpenFOAM-12/etc/bashrc"
unset DISPLAY; export HWLOC_COMPONENTS=-gl
cd "$HOME/windtunnel/openfoam/airframe-sweep" || exit 1
export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
CASE=$HOME/sweep_t1/case_V15_a20_b0_probe
rm -rf "$CASE"
bash make_case.sh 15 20 0 "$CASE" > /dev/null 2>&1
# 大攻角治愈配方预置: p/U 0.5 (SIGFPE 家族预防)
sed -i 's/p               0.9;/p               0.5;/' "$CASE/system/fvSolution"
sed -i 's/U               0.9;/U               0.5;/' "$CASE/system/fvSolution"
bash run_solve.sh "$CASE" 6 2000 > "$HOME/sweep_t1/log.probe_V15_a20_b0" 2>&1
echo "CPU probe rc=$? $(date)"
tail -2 "$HOME/sweep_t1/case_V15_a20_b0/log.foamRun" 2>/dev/null
