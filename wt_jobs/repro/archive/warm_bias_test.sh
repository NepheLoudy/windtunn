#!/usr/bin/env bash
# 热启动有偏性验证: 从 smoke3(20,5,0 已收敛) 热启动到同点 V=20, 短跑 200 步
# 判据: 六系数与 smoke3 冷启动结果一致 (<2%/<0.005 绝对), 且收敛更快
set +e
source /opt/openfoam12/etc/bashrc
set -e
unset DISPLAY; export HWLOC_COMPONENTS=-gl

A=/mnt/d/WindTunnelSuite/openfoam/airframe-sweep
S3=/mnt/d/WindTunnelSuite/wt_jobs/tmp/smoke3
W=/mnt/d/WindTunnelSuite/wt_jobs/tmp/warm_bias_in
cd "$A"

rm -rf "$W"
echo "[1/3] warm clone (V=20 同点)"
WARM_FROM=$S3 bash clone_case.sh $S3 $W 20

echo "[2/3] solve 200 步 (热启动应极快收敛)"
bash run_solve.sh $W 8 200 > /tmp/warm_bias_solve.log 2>&1

echo "[3/3] post_process"
python3 post_process.py $W --mass-props cad/v1/cfd/mass_properties.json \
  --json $W/results.json --out $W/warm_table.csv 2>&1 | tail -4

echo "=== 对照 ==="
echo "冷启动(smoke3, 600步): $(tail -1 $S3/smoke3_table.csv)"
echo "热启动(warm,   200步): $(tail -1 $W/warm_table.csv)"
echo "=== BIAS TEST DONE $(date +%H:%M:%S) ==="
