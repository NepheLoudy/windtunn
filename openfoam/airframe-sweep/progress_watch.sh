#!/usr/bin/env bash
# 进度看门狗: 轮询 sweep.log/结果表, 写 progress.json (Windows 悬浮窗数据源)
#   usage: progress_watch.sh <anchor_root> <total> <batch_name>
#   例:  progress_watch.sh ~/openfoam/airframe-sweep/anchor 24 "锚定批次"
set -u

ROOT=${1:?usage: progress_watch.sh <root> <total> <batch_name>}
TOTAL=${2:?usage: progress_watch.sh <root> <total> <batch_name>}
BATCH=${3:?usage: progress_watch.sh <root> <total> <batch_name>}
OUT=${PROGRESS_JSON:-"/mnt/d/WindTunnelSuite/openfoam/airframe-sweep/progress.json"}
LOG="$ROOT/sweep.log"
T0=$(date +%s)

while true; do
  NOW=$(date +%s)
  RUN_MIN=$(( (NOW - T0) / 60 ))
  DONE=$(grep -c '"coeffs"' "$ROOT"/*/results.json 2>/dev/null | grep -c ':1$' 2>/dev/null)
  [ -z "$DONE" ] && DONE=0
  # 当前工况 = sweep.log 最后一个 ===== [n] tag
  CUR=$(grep -o '===== \[[0-9]*\] [^ ]*' "$LOG" 2>/dev/null | tail -1 | awk '{print $3}')
  STEP=$(grep -o 'meshing\|solved: [^(]*' "$LOG" 2>/dev/null | tail -1)
  [ -z "$STEP" ] && STEP="..."
  DONE_FLAG=0
  ETA=-1
  if grep -q "扫气完成" "$LOG" 2>/dev/null; then
    DONE_FLAG=1
    RESULTS=$(grep -v pop_var "$LOG" 2>/dev/null | grep "扫气完成" | tail -1)
    ETA=0
  else
    if [ "$DONE" -gt 0 ]; then
      PER=$(( (NOW - T0) / DONE ))
      ETA=$(( (TOTAL - DONE) * PER / 60 ))
    fi
  fi
  RESULTS=${RESULTS:-""}
  cat > "$OUT" <<EOF
{"batch":"$BATCH","done":$DONE,"total":$TOTAL,"current":"$CUR","step":"$STEP","run_min":$RUN_MIN,"eta_min":$ETA,"done_flag":$DONE_FLAG,"results":"$RESULTS","ts":$NOW}
EOF
  if [ "$DONE_FLAG" = "1" ]; then break; fi
  sleep 15
done
