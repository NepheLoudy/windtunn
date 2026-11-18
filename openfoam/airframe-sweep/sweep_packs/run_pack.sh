#!/usr/bin/env bash
# 领包执行器 — 一台机器领一个任务包, 输出独立表 + 状态回报
#   usage: run_pack.sh <PACK_ID> [WORK_ROOT]
#   产出: WORK_ROOT/<PACK_ID>/table.csv (合并用 collect.sh)
#         WORK_ROOT/<PACK_ID>/status.json (看板)
#   纪律: env 三件套自检不过不发车 (11-17 裸环境事故);
#         不用 eval/嵌套 heredoc 解析参数 (多层引号会咬; 2026-11-18 实测)
set +u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SWEEP_DIR=$(cd "$HERE/.." && pwd)

PACK=${1:?usage: run_pack.sh <PACK_ID> [WORK_ROOT]}
WORK_ROOT=${2:-$HOME/sweep_pack_work}
PACK_JSON="$HERE/packs/$PACK.json"
[ -f "$PACK_JSON" ] || { echo "FATAL: 无包定义 $PACK_JSON"; exit 1; }

# --- OpenFOAM env (显式 source) ---
for rc in "${FOAM_BASHRC:-}" /opt/openfoam12/etc/bashrc "$HOME/OpenFOAM-12/etc/bashrc" \
          /usr/lib/openfoam/openfoam12/etc/bashrc; do
  if [ -n "$rc" ] && [ -f "$rc" ]; then source "$rc" 2>/dev/null; EOF_RC="$rc"; break; fi
done
set -e
unset DISPLAY; export HWLOC_COMPONENTS=-gl

for t in blockMesh snappyHexMesh foamRun; do
  command -v "$t" >/dev/null || { echo "FATAL: $t 不在 PATH (bashrc=${EOF_RC:-none})"; exit 1; }
done

# --- 读包参数 (逐项 python -c + argv, 无 eval) ---
pyget() { python3 -c "import json,sys;p=json.load(open(sys.argv[1]));print(eval(sys.argv[2]))" "$PACK_JSON" "$1"; }
PACK_ID=$(pyget 'p["pack_id"]')
SWEEP_V=$(pyget '" ".join(str(v) for v in p["V"])')
SURF_LEVEL=$(pyget 'p["env"]["SURF_LEVEL"]')
FIN_LEVEL=$(pyget 'p["env"]["FIN_LEVEL"]')
BOX_LEVEL=$(pyget 'p["env"]["BOX_LEVEL"]')
NP=$(pyget 'p["env"]["NP"]')
CASES=$(pyget 'p["cases"]')
GROUPS_N=$(pyget 'len(p["groups"])')

ROOT="$WORK_ROOT/$PACK_ID"
mkdir -p "$ROOT"
OUT_CSV="$ROOT/table.csv"
export GEOM_DIR="$SWEEP_DIR/cad/v1/cfd_geom_multi_parallel"

echo "=== PACK $PACK_ID 领包 $(date '+%F %T') ==="
echo "groups=$GROUPS_N cases=$CASES V=$SWEEP_V"
echo "SURF=$SURF_LEVEL FIN=$FIN_LEVEL BOX=$BOX_LEVEL NP=$NP"
echo "root=$ROOT  blockMesh=$(command -v blockMesh)"

cat > "$ROOT/status.json" <<JSON
{"pack_id":"$PACK_ID","status":"running","host":"$(hostname)","pid":$$,
 "started":"$(date +%FT%T%z)","groups":$GROUPS_N,"cases":$CASES,"rows":0}
JSON

cd "$SWEEP_DIR" || exit 1
# 逐组跑 (包内 (α,β) 是任意配对, 不能靠 α×β 笛卡尔积; 单组 = 全 V, 保网格复用+热启动)
python3 -c "
import json,sys
for g in json.load(open(sys.argv[1]))['groups']:
    print('%s %s' % (g['alpha'], g['beta']))" "$PACK_JSON" |
PACK_FAIL=0
while read -r A B; do
  echo "----- [$(date +%H:%M:%S)] group alpha=$A beta=$B -----"
  if OUT_CSV="$OUT_CSV" SWEEP_V="$SWEEP_V" SWEEP_ALPHA="$A" SWEEP_BETA="$B" \
  SURF_LEVEL=$SURF_LEVEL FIN_LEVEL=$FIN_LEVEL BOX_LEVEL=$BOX_LEVEL \
  GEOM_DIR="$GEOM_DIR" \
    ./run_sweep_v2.sh "$ROOT/g_a${A}_b${B}" "$NP" >> "$ROOT/pack.log" 2>&1; then
    :
  else
    echo "  group alpha=$A beta=$B 有失败例 (继续下一组)"
    PACK_FAIL=$((PACK_FAIL+1))
  fi
done

ROWS=$(python3 -c "
import sys,os
p=sys.argv[1]
n=0
if os.path.exists(p):
    for l in open(p,encoding='utf-8',errors='replace'):
        if l.strip() and not l.startswith('#') and not l.startswith('V,'):
            n+=1
print(n)" "$OUT_CSV")
# 状态诚实化 (A1, 2026-11-19 审查): rows<cases 或组有失败 → partial, 禁写 done
if [ "$ROWS" -ge "$CASES" ] && [ "$PACK_FAIL" -eq 0 ]; then
  ST="done"
elif [ "$ROWS" -gt 0 ] || [ "$PACK_FAIL" -gt 0 ]; then
  ST="partial"
else
  ST="failed"
fi
cat > "$ROOT/status.json" <<JSON
{"pack_id":"$PACK_ID","status":"$ST","host":"$(hostname)",
 "finished":"$(date +%FT%T%z)","groups":$GROUPS_N,"cases":$CASES,"rows":$ROWS,"group_fail":$PACK_FAIL}
JSON
echo "PACK $PACK_ID $ST rows=$ROWS/$CASES group_fail=$PACK_FAIL"
