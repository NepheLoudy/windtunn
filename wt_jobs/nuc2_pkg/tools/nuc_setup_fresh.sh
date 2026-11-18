#!/bin/bash
# NUC WSL: 验证 OpenFOAM + git clone 仓库 + 领包 (镜像缺仓库时用这个)
set -x
echo "=== [1] OpenFOAM ==="
source /opt/openfoam12/etc/bashrc 2>/dev/null || source ~/openfoam/openfoam12/etc/bashrc 2>/dev/null
BM=$(command -v blockMesh)
echo "blockMesh: $BM"
[ -z "$BM" ] && { echo "FATAL: no blockMesh — checking alternatives"; ls /opt/ 2>/dev/null; ls ~/openfoam* -d 2>/dev/null; }

echo "=== [2] git + clone ==="
command -v git || apt-get install -y git -q 2>/dev/null
mkdir -p /root/work && cd /root/work
[ -d windtunnel ] || git clone --depth 1 https://github.com/NepheLoudy/windtunn windtunnel 2>&1 | tail -2
ls windtunnel/openfoam/airframe-sweep/sweep_packs/packs/*.json 2>/dev/null | wc -l

echo "=== [3] keepalive ==="
pgrep -f 'sleep 300' >/dev/null || (setsid nohup bash -c 'while :; do sleep 300; done' >/dev/null 2>&1 &)
echo "keepalive: $(pgrep -cf 'sleep 300')"

echo "=== [4] 领包 ==="
PACK=${1:-P05}
cd /root/work/windtunnel/openfoam/airframe-sweep/sweep_packs
setsid nohup bash run_pack.sh "$PACK" > "/tmp/pack_${PACK}.log" 2>&1 < /dev/null &
sleep 10
echo "runners: $(pgrep -cf run_sweep_v2)"
tail -6 "/tmp/pack_${PACK}.log" 2>/dev/null
echo "=== SETUP_DONE ==="
