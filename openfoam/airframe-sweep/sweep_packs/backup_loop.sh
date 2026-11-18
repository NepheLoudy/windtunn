#!/usr/bin/env bash
# 包进度周期回备 — WSL ext4 (/root/sweep_pack_work) -> /mnt/d 持久盘
# 原因: WSL VM 关闭 = ext4 上的 case/结果丢失(tmpfs/VM 生命周期), 而 ext4 跑 OpenFOAM 比 9p 快
# 频率: 每 10 min 拷 table.csv + status.json (小文件, 秒级)
set -uo pipefail
SRC=${1:-/root/sweep_pack_work}
DST=${2:-/mnt/d/WindTunnelSuite/wt_jobs/tmp/sweep_pack_backup}
mkdir -p "$DST"
while :; do
  for p in "$SRC"/*/; do
    [ -d "$p" ] || continue
    pid=$(basename "$p")
    mkdir -p "$DST/$pid"
    [ -f "$p/table.csv" ] && cp -f "$p/table.csv" "$DST/$pid/" 2>/dev/null
    [ -f "$p/status.json" ] && cp -f "$p/status.json" "$DST/$pid/" 2>/dev/null
  done
  date '+%F %T backup ok' >> "$DST/.backup.log"
  sleep 600
done
