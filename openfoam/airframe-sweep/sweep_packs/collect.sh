#!/usr/bin/env bash
# 回填 — 汇总所有包的 table.csv → 单一 T1 表 (六键判重 + 表头一致性核对)
#   usage: collect.sh <OUT_CSV> <WORK_ROOT> [MORE_WORK_ROOTS...]
#   依赖 ../merge_master.py (E2): 表头必须同源, 重复键按来源优先级取档并报告
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SWEEP_DIR=$(cd "$HERE/.." && pwd)

OUT=${1:?usage: collect.sh <OUT_CSV> <WORK_ROOT> [more roots...]}
shift
[ $# -ge 1 ] || { echo "FATAL: 需要至少一个 WORK_ROOT"; exit 1; }

ARGS=()
for root in "$@"; do
  for f in "$root"/*/table.csv; do
    [ -f "$f" ] || continue
    # source = 包 ID (目录名, 如 P01s1) — 保留来源分档与判重归属, 不再统一标 t1
    pid=$(basename "$(dirname "$f")")
    ARGS+=(--local "$f:$pid")
  done
done
[ ${#ARGS[@]} -gt 0 ] || { echo "FATAL: 没找到任何 table.csv"; exit 1; }

echo "=== 合并 ${#ARGS[@]} 个包表 -> $OUT ==="
python3 "$SWEEP_DIR/merge_master.py" "${ARGS[@]}" --out "$OUT"
rc=$?
if [ $rc -eq 0 ]; then
  python3 - "$OUT" <<'PY'
import sys
p = sys.argv[1]
rows = sum(1 for l in open(p, encoding="utf-8", errors="replace")
           if l.strip() and not l.startswith("#") and not l.startswith("V,"))
print("master rows = %d -> %s" % (rows, p))
PY
fi
exit $rc
