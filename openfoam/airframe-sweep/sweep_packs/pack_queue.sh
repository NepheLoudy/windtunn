#!/usr/bin/env bash
# pack_queue.sh — 队列续包器: 固定槽位数(默认2), 包完了自动领下一个
#   usage: bash pack_queue.sh <NP> <SLOTS> <PACK_ID...>
#   例:   bash pack_queue.sh 7 2 P02 P03 P10 P11 P16 P17
#   与 run_pack.sh 判重协同: 重复跑会自动跳过已完成例, 不会重算
SW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NP="${1:?usage: pack_queue.sh <NP> <SLOTS> <PACK...>}"
SLOTS="${2:?usage: pack_queue.sh <NP> <SLOTS> <PACK...>}"
shift 2
ROOT="$HOME/sweep_pack_work"
mkdir -p "$ROOT"

echo "[$(date '+%F %T')] queue start  NP=$NP SLOTS=$SLOTS  packs: $*"
QUEUE=("$@")
RUNNING=0
declare -A PID2PACK

launch() {
  local pack="$1"
  echo "[$(date '+%F %T')] LAUNCH $pack (NP=$NP)"
  ( cd "$SW_DIR" && PACK_NP="$NP" bash run_pack.sh "$pack" "$ROOT" >> "$ROOT/$pack.outer.log" 2>&1 ) &
  PID2PACK[$!]="$pack"
}

for p in "${QUEUE[@]}"; do
  while [ "$RUNNING" -ge "$SLOTS" ]; do
    wait -n 2>/dev/null || sleep 30
    # 回收已完成
    for pid in "${!PID2PACK[@]}"; do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "[$(date '+%F %T')] DONE ${PID2PACK[$pid]}"
        unset "PID2PACK[$pid]"
        RUNNING=$((RUNNING-1))
      fi
    done
  done
  launch "$p"
  RUNNING=$((RUNNING+1))
  sleep 8
done

echo "[$(date '+%F %T')] all packs dispatched, waiting for tail..."
wait
echo "[$(date '+%F %T')] QUEUE COMPLETE"
for p in "${QUEUE[@]}"; do
  st=$(python3 -c "import json;print(json.load(open('$ROOT/$p/status.json'))['status'])" 2>/dev/null || echo "?")
  rows=$(python3 -c "import json;print(json.load(open('$ROOT/$p/status.json'))['rows'])" 2>/dev/null || echo "?")
  echo "  $p: $st rows=$rows"
done
