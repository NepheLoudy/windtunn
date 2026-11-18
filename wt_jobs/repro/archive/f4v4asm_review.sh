#!/usr/bin/env bash
# F4 v4asm 重扫前两例 lockin 复审 (11-10 半途审查)
for t in p_f1:0.012566 p_f2:0.0031416; do
  n=${t%%:*}; w=${t##*:}
  echo "== $n (omega=$w)"
  python3 ~/fluidx3d_v3/FluidX3D-master/bin/lockin.py \
    ~/fluidx3d_v3/FluidX3D-master/bin/out/forces_osc_${n}_v4asm.csv "$w" 200000 2>/dev/null \
    | grep -E 'ch|fz |ty |tz |tx '
done
echo "== d0 静基线 DC 对照"
tail -1 ~/fluidx3d_v3/FluidX3D-master/bin/out/forces_d0.csv
