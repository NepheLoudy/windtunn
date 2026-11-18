#!/usr/bin/env bash
# 看板 — 任务包状态总览 (本地 + 远端聚合)
#   usage: board.sh [WORK_ROOT] [HOST:WORK_ROOT ...]
#   读每个 $WORK_ROOT/<PACK>/status.json, 汇总 pending/running/done/failed 与行数
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_ROOT=${1:-$HOME/sweep_pack_work}

echo "=== 任务包看板 $(date '+%F %T') ==="
echo "-- 包定义 --"
python3 - "$HERE/packs/index.json" <<'PY'
import json, sys
idx = json.load(open(sys.argv[1], encoding="utf-8"))
print("域: V=%s" % idx["domain"]["V"])
print("     α=%s" % idx["domain"]["alpha"])
print("     β=%s" % idx["domain"]["beta"])
print("总: %d 组 / %d 例 / %d 包" % (idx["total_groups"], idx["total_cases"], len(idx["packs"])))
PY

echo "-- 本机执行状态 ($LOCAL_ROOT) --"
python3 - "$LOCAL_ROOT" "$HERE/packs" <<'PY'
import glob, json, os, sys
root, pdir = sys.argv[1], sys.argv[2]
all_defs = {os.path.basename(p)[:-5]: json.load(open(p, encoding="utf-8"))
            for p in glob.glob(os.path.join(pdir, "P*.json"))}
# 分片 (带 parent) 代表父包的执行 — 父包从合计中排除, 防双计数 (2026-11-19 审查)
sharded_parents = {d.get("parent") for d in all_defs.values() if d.get("parent")}
shards = sorted(p for p, d in all_defs.items() if d.get("parent"))
defs = {pid: d for pid, d in all_defs.items() if pid not in sharded_parents}
if sharded_parents:
    print("  (分片接管: %s → 由 %s 代表)" % (",".join(sorted(sharded_parents)), ",".join(shards)))
tot_done = tot = 0
rows = 0
for pid in sorted(defs):
    st_p = os.path.join(root, pid, "status.json")
    d = defs[pid]
    tot += d["cases"]
    if os.path.exists(st_p):
        st = json.load(open(st_p, encoding="utf-8"))
        r = st.get("rows", 0)
        rows += r
        tot_done += r
        print("  %s %-8s %-8s rows=%-4d /%d  %s" % (pid, st.get("status", "?"),
              st.get("host", ""), r, d["cases"], st.get("finished", st.get("started", ""))))
    else:
        print("  %s pending  -        /%d" % (pid, d["cases"]))
print("\n  合计: %d / %d 例 (%.1f%%)" % (tot_done, tot, 100.0 * tot_done / max(tot, 1)))
PY
