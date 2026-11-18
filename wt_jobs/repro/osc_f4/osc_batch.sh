#!/usr/bin/env bash
# F4 dynamic-derivative batch runner (11-08, RTX 5070)
# 3 axes (1=pitch Cmq / 2=yaw Cnr / 3=roll Clp) x 2 frequencies = 6 cases, 1.2M steps each (~90 min/case)
# freq points: omega=0.012566 (500 steps/cycle, 2400 cycles) and omega=0.0031416 (2000 steps/cycle, 600 cycles)
# fixed: ALPHA=5 BETA=0 AMP=2deg NX=440 NU=0.02 GEOM=cfd_v4parts; lock-in window: skip first 200k steps
cd ~/fluidx3d_v3/FluidX3D-master/bin || exit 1
run_case () {
  local AX=$1 OM=$2 TAG=$3
  if [ -s "out/forces${TAG}.csv" ] && [ "$(grep -c . "out/forces${TAG}.csv")" -ge 12001 ]; then
    echo "skip $TAG (exists)"; return
  fi
  echo "=== OSC axis=$AX omega=$OM TAG=$TAG start $(date '+%m-%d %H:%M:%S') ==="
  GEOM_DIR=cfd_v4parts/ STEPS=1200000 OSC_AXIS=$AX OSC_AMP=2.0 OSC_FREQ=$OM \
    ALPHA=5 BETA=0 NX=440 NU=0.02 TAG=$TAG ./FluidX3D > "osc${TAG}.log" 2>&1
  echo "=== OSC axis=$AX omega=$OM TAG=$TAG done  $(date '+%m-%d %H:%M:%S') rc=$? ==="
  python3 lockin.py "out/forces${TAG}.csv" $OM 200000 100
}
run_case 1 0.012566 _osc_p_f1
run_case 1 0.0031416 _osc_p_f2
run_case 2 0.012566 _osc_y_f1
run_case 2 0.0031416 _osc_y_f2
run_case 3 0.012566 _osc_r_f1
run_case 3 0.0031416 _osc_r_f2
echo "=== F4 OSC batch done $(date) ==="
