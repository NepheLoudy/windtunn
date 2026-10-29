#!/usr/bin/env bash
# case 收割机: 完成工况的场数据清理 (防 T1 磁盘爆仓 473G>265G, 10-30)
# 规则: results.json 存在 + 目录 30 分钟未动 才动手
# 保留: constant/(组网格源) system postProcessing results.json log.* CASEINFO
# 删除: processor* 整目录 (重启动=decomposePar -force 再生) + 顶层重构时间目录
# 保护: constant(组网格源) system 0(初始场, clone 依赖) postProcessing results.json
ROOT=${1:?usage: case_reaper.sh <sweep_root> [interval_s]}
IV=${2:-600}
cd "$ROOT" || exit 1
echo "reaper watching $ROOT every ${IV}s"
while true; do
  for d in case_*/; do
    [ -f "$d/results.json" ] || continue
    if [ -n "$(find "$d" -newermt "-30 minutes" -print -quit 2>/dev/null)" ]; then continue; fi
    before=$(du -sm "$d" | cut -f1)
    rm -rf "$d"processor* 2>/dev/null
    find "$d" -maxdepth 1 -regextype posix-extended -regex ".*/[0-9]+(.[0-9]+)?" -not -name constant -not -name 0 -exec rm -rf {} + 2>/dev/null
    after=$(du -sm "$d" | cut -f1)
    if [ "$before" != "$after" ]; then echo "$(date +%m-%d\ %H:%M) slimmed $d ${before}M -> ${after}M"; fi
  done
  sleep "$IV"
done
