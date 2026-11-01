#!/usr/bin/env bash
# T2 大攻角瞬态批次 runner (11-01, 5070 每例 300k 步 ~4min)
# 批次: α ∈ {±12.5, ±15} × β ∈ {0, ±5} = 12 例 — 非对称涡分支区扫描
# 语义: 每例独立稳态 → fy(fx) 分布 = 分支不确定性量化; FVM 蓝表同工况对拍
cd ~/fluidx3d_v3/FluidX3D-master/bin || exit 1
for A in 12.5 -12.5 15 -15; do
  for B in 0 5 -5; do
    TAG="_a${A}_b${B}"
    if [ -s "out/forces${TAG}.csv" ] && [ "$(grep -c . "out/forces${TAG}.csv")" -ge 60 ]; then
      echo "skip $TAG (exists)"; continue
    fi
    echo "=== ALPHA=$A BETA=$B $(date +%H:%M:%S) ==="
    GEOM_DIR=cfd_v4parts/ STEPS=300000 ALPHA=$A BETA=$B TAG=$TAG ./FluidX3D > "t2${TAG}.log" 2>&1
  done
done
echo "=== T2 batch done $(date) ==="
for f in out/forces_a*_b*.csv; do
  echo "$f: $(tail -1 "$f")"
done
