#!/usr/bin/env bash
# 任务包发车前自检 + 发车 (脚本化, 避免多层引号)
#   usage: launch_packs.sh <PACK_ID...>        (本机)
#          launch_packs.sh --debug <PACK_ID>   (只自检不发车)
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

DEBUG=0
if [ "${1:-}" = "--debug" ]; then DEBUG=1; shift; fi
[ $# -ge 1 ] || { echo "usage: launch_packs.sh [--debug] <PACK_ID...>"; exit 1; }

echo "=== 1. 解析自检 ==="
for P in "$@"; do
  PJ="$HERE/packs/$P.json"
  [ -f "$PJ" ] || { echo "FATAL 包不存在: $PJ"; exit 1; }
  python3 - "$PJ" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
print("  %s: cases=%d groups=%d V=%s"
      % (p["pack_id"], p["cases"], len(p["groups"]),
         ",".join(str(v) for v in p["V"])))
print("     first group: alpha=%s beta=%s"
      % (p["groups"][0]["alpha"], p["groups"][0]["beta"]))
PY
done

if [ $DEBUG -eq 1 ]; then echo "=== debug 模式, 不发车 ==="; exit 0; fi

echo "=== 2. 发车 ==="
for P in "$@"; do
  LOG="/tmp/pack_${P}.log"
  setsid nohup bash "$HERE/run_pack.sh" "$P" > "$LOG" 2>&1 < /dev/null &
  echo "  $P -> $LOG (pid $!)"
  sleep 3
done
sleep 5
echo "=== 3. runner 计数 ==="
pgrep -cf 'run_sweep_v[2]' || echo "  0 (可能仍在建 case 阶段)"
echo "=== 4. 各包日志头 ==="
for P in "$@"; do
  echo "--- $P ---"
  head -6 "/tmp/pack_${P}.log" 2>/dev/null
done
