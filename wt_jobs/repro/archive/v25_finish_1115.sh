#!/usr/bin/env bash
# =============================================================================
# V25 a0_b0 收尾看护 v2 — 孤儿链手工接管 (2026-11-15)
# 背景: cure_final_1115 看护被第一治愈工位止血击杀 (合理: 当时 r1 脏场),
#       但 V25 的 post_process→落表→CY 锚→终验链随之孤儿化, 本脚本接管。
# 在跑: V25 r2 (13:08 发射 np=6 ET1500, 治愈配方 fvSolution 未被重置)。
# 纪律: flock 双层互斥 (case 级 + 表级), 防多工位同 case 再撞 (16GB OOM 教训)
# =============================================================================
set -u
AF=/home/qianli/windtunnel/openfoam/airframe-sweep
ROOT=/home/qianli/sweep_t0v2
CASE=$ROOT/case_V25_a0_b0
T0T=$ROOT/t0_table.csv
LOG=$ROOT/cure_V25_final_1115.log
LOCK=/tmp/v25_a0b0.finish.lock

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# ---- 双层互斥: 本脚本单实例 + case 操作锁 ----
exec 9>"$LOCK"
if ! flock -n 9; then echo "another finisher is running"; exit 1; fi
log "=== V25 收尾看护接管启动 (r2 在跑, 等 1500 步) ==="

nsteps() { local n; n=$(grep -ac '^Time = ' "$CASE/log.foamRun" 2>/dev/null || true); echo "${n:-0}"; }
fped()   { grep -aq "Floating point exception" "$CASE/log.foamRun" 2>/dev/null; }
solving() { ps -eo cmd | grep -v grep | grep -q "run_solve.sh $CASE "; }
in_table() { awk -F, 'NR>2 && $1=="25.0000" && $2=="0.0000" && $3=="0.0000"{f=1} END{exit !f}' "$T0T"; }

# ---- Phase 1: 等 r2 跑完 (最长 3h) ----
i=0
while solving; do
  sleep 120; i=$((i+1))
  [ $((i % 5)) -eq 0 ] && log "poll: V25 r2 = $(nsteps)步, FPE=$(fped && echo Y || echo N)"
  [ $i -gt 90 ] && { log "等待超时 3h — 退出回报"; exit 2; }
done
log "r2 已退出: $(nsteps)步 FPE=$(fped && echo Y || echo N)"

# ---- Phase 2: 判定 ----
if fped; then
  log "r2 SIGFPE — 按任务卡升级配方 r3 ((k|omega) 0.85→0.5, np=6, flock 串行)"
  CASE=$CASE flock /tmp/v25.case.lock bash -c "
    sed -i -E 's/^([[:space:]]+\\\"\\\(k\\\|omega\\\)\\\"[[:space:]]+)0\\.85;$/\\10.5;/' '$CASE/system/fvSolution'
    find '$CASE' -maxdepth 1 -type d -regextype posix-extended -regex '.*/[0-9]+' ! -name '0' -exec rm -rf {} +
    rm -f '$CASE/postProcessing/forces/0/forces.dat' '$CASE/log.foamRun'
  "
  grep -qE '"\(k\|omega\)"[[:space:]]+0\.5;' "$CASE/system/fvSolution" \
    && log "r3 配方已上 (k|omega 0.5)" || { log "r3 配方 sed 失败 — 停手回报"; exit 3; }
  "$AF/run_solve.sh" "$CASE" 6 1500 >> "$LOG" 2>&1 || true
  log "r3 完成: $(nsteps)步 FPE=$(fped && echo Y || echo N)"
  if fped || [ "$(nsteps)" -lt 1500 ]; then
    log "r3 仍败 — 两轮败, 按任务卡停手回报"; exit 4
  fi
fi

NS=$(nsteps)
if [ "$NS" -lt 1500 ] 2>/dev/null; then
  log "非常规退出 ($NS 步, 非 FPE 非满步) — 不落表, 停手回报"; exit 5
fi

# ---- Phase 3: 落表 (flock 表级串行, 防并发 append 撕行) ----
if in_table; then
  log "V25 已在表 — 跳过 postproc"
else
  flock /tmp/t0_table.csv.lock bash -c "
    python3 '$AF/post_process.py' '$CASE' \
      --mass-props '$AF/cad/v1/cfd/mass_properties.json' \
      --json '$CASE/results.json' --out '$T0T'" >> "$LOG" 2>&1 \
    || { log "post_process 命令失败"; exit 6; }
  in_table && log "V25 a0_b0 落表 OK" || { log "落表后行未出现 — 异常"; exit 7; }
fi

# ---- Phase 4: 终态验证 (546/546 + CY 锚 + 残差) ----
python3 - "$T0T" >> "$LOG" 2>&1 <<'PY'
import csv, json, sys
t = sys.argv[1]
have = {}
for r in csv.reader(open(t)):
    if not r or r[0].startswith('#'): continue
    try: have[(float(r[0]), float(r[1]), float(r[2]))] = r
    except: pass
alphas = [-15,-12.5,-10,-7.5,-5,-2.5,0,2.5,5,7.5,10,12.5,15]
betas  = [-15,-10,-5,0,5,10,15]
target = [(V,a,b) for V in [20,21,22,23,24,25] for a in alphas for b in betas]
missing = [k for k in target if k not in have]
print("in-target %d/546  missing=%s" % (len(target)-len(missing), missing))
for V in (24, 25):
    k = (float(V), 0.0, 0.0)
    if k in have:
        r = have[k]; cy = float(r[9])
        print("V%d a0_b0: CL=%s CD=%s Cm=%s CY=%s Cn=%s  |CY|<0.03 锚: %s"
              % (V, r[6], r[7], r[8], r[9], r[11], "PASS" if abs(cy) < 0.03 else "FAIL"))
        try:
            j = json.load(open("/home/qianli/sweep_t0v2/case_V%d_a0_b0/results.json" % V))
            print("V%d results.json: residual_rel=%.4f n_samples=%d" % (V, j["residual_rel"], j["n_samples"]))
        except Exception as e:
            print("V%d results.json 读取失败: %s" % (V, e))
# 全表六档 a0_b0 CY 锚
for V in (20,21,22,23,24,25):
    k=(float(V),0.0,0.0)
    if k in have: print("V%d CY=%.6f %s" % (V, float(have[k][9]), "PASS" if abs(float(have[k][9]))<0.03 else "FAIL"))
PY
log "=== V25 收尾看护结束 ==="
