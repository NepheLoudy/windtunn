#!/usr/bin/env bash
# 在算力节点上一次性: 清理→启动 T1→立刻回显状态 (用于验证启动是否真的生效)
set -u
pkill -9 -f run_sweep_v2 2>/dev/null
pkill -9 -f foamRun 2>/dev/null
sleep 2
rm -rf ~/sweep_t1
mkdir -p ~/sweep_t1
cd ~/windtunnel/openfoam/airframe-sweep || exit 1
./launch_t1.sh > /tmp/launch_out.txt 2>&1
echo "--- launch output ---"
cat /tmp/launch_out.txt
sleep 20
echo "--- sweep.log head ---"
head -5 ~/sweep_t1/sweep.log 2>/dev/null
echo "--- procs ---"
pgrep -af run_sweep_v2 | head -2
pgrep -c foamRun
