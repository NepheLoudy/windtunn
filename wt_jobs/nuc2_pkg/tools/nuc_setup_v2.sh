#!/bin/bash
# NUC WSL setup v2: clone from local bundle (no GitHub) + keepalive + claim pack
echo "=== [1] OpenFOAM ==="
source /opt/openfoam12/etc/bashrc 2>/dev/null
echo "blockMesh: $(command -v blockMesh)"

echo "=== [2] clone from bundle ==="
mkdir -p /root/work
cd /root/work
if [ ! -d windtunnel ]; then
  git clone /mnt/d/nuc_repo.bundle windtunnel 2>&1 | tail -1
  cd windtunnel && git remote set-url origin https://github.com/NepheLoudy/windtunn && git checkout main 2>&1 | tail -1
fi
P=$(ls /root/work/windtunnel/openfoam/airframe-sweep/sweep_packs/packs/*.json 2>/dev/null | wc -l)
echo "packs: $P"

echo "=== [3] keepalive ==="
pgrep -f 'sleep 300' >/dev/null || (setsid nohup bash -c 'while :; do sleep 300; done' >/dev/null 2>&1 &)
echo "keepalive: $(pgrep -cf 'sleep 300')"

echo "=== [4] claim pack ==="
PACK=${1:-P05}
cd /root/work/windtunnel/openfoam/airframe-sweep/sweep_packs
setsid nohup bash run_pack.sh "$PACK" > "/tmp/pack_${PACK}.log" 2>&1 < /dev/null &
sleep 12
echo "runners: $(pgrep -cf run_sweep_v2)"
tail -6 "/tmp/pack_${PACK}.log" 2>/dev/null
echo "=== SETUP_V2_DONE ==="
