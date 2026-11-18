#!/bin/bash
# NUC WSL 环境验证 + keepalive + 领包 (scp 后由主会话触发执行)
echo "=== [1] OpenFOAM ==="
source /opt/openfoam12/etc/bashrc 2>/dev/null
echo "blockMesh: $(command -v blockMesh)"
echo "=== [2] 仓库 ==="
echo "packs: $(ls /root/windtunnel/openfoam/airframe-sweep/sweep_packs/packs/ 2>/dev/null | grep -c json)"
echo "=== [3] 硬件 ==="
echo "cores: $(nproc)"
free -g | head -2
echo "=== [4] keepalive ==="
pgrep -f 'sleep 300' >/dev/null || (setsid nohup bash -c 'while :; do sleep 300; done' >/dev/null 2>&1 &)
echo "keepalive procs: $(pgrep -cf 'sleep 300')"
echo "=== [5] 领包 ==="
PACK=${1:-P05}
cd /root/windtunnel/openfoam/airframe-sweep/sweep_packs
setsid nohup bash run_pack.sh "$PACK" > "/tmp/pack_${PACK}.log" 2>&1 < /dev/null &
sleep 10
echo "pack $PACK: $(pgrep -cf run_sweep_v2) runner(s) alive"
tail -5 "/tmp/pack_${PACK}.log" 2>/dev/null
echo "=== VERIFY_DONE ==="
