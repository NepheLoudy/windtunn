#!/usr/bin/env bash
# =============================================================================
# T0 全表 546/546 收官看护 — V24 orphan 收编 + V25 重建治愈 (r1 → r2)
# 2026-11-15 | T0 治愈续航 (前工位 21/22 入库后殉职, V24 r1 orphan 在跑)
# 配方 (21/22 成功例实测): fvSolution 松弛 p 0.5 / U 0.5 / (k|omega) 0.85,
#   endTime 1500, make_case(V 0 0, GEOM=cfd_geom_multi_parallel, SURF5/FIN7/BOX3)
# r2 升级配方 (仍 SIGFPE 才用): (k|omega) 0.85→0.5, 其余同 — 两轮败停手
# 纪律: 舵效批 (delta np=7×2) 绝不 pkill; 治愈例 np=6 错峰 (1.4x 容忍线内)
# =============================================================================
set -u
AF=/home/qianli/windtunnel/openfoam/airframe-sweep
ROOT=/home/qianli/sweep_t0v2
T0T=$ROOT/t0_table.csv
LOG=$ROOT/cure_final_1115.log

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# ---- 单例锁: 防双看护 ----
LOCK=$ROOT/.cure_final_1115.lock
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "watcher already running (pid $(cat "$LOCK"))"; exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

: > "$LOG"
log "=== T0 收官看护启动: V24 收编 (orphan r1 np=8) + V25 重建 r1 np=6 ==="
log "load: $(uptime)"

nsteps() { local n; n=$(grep -c '^Time = ' "$1/log.foamRun" 2>/dev/null || true); echo "${n:-0}"; }
fped()   { grep -q "Floating point exception" "$1/log.foamRun" 2>/dev/null; }
running() { ps -eo cmd | grep -v grep | grep -q "run_solve.sh $1 "; }
in_table() { awk -F, -v v="$1.0000" 'NR>2 && $1==v && $2=="0.0000" && $3=="0.0000"{f=1} END{exit !f}' "$T0T"; }

postproc() {  # $1=V → 力系数落表 (带表级防重)
  local V=$1 CASE=$ROOT/case_V${V}_a0_b0
  if in_table "$V"; then log "V$V a0_b0 已在表 — 跳过 postproc"; return 0; fi
  if ! python3 "$AF/post_process.py" "$CASE" \
      --mass-props "$AF/cad/v1/cfd/mass_properties.json" \
      --json "$CASE/results.json" --out "$T0T" >> "$LOG" 2>&1; then
    log "V$V post_process 命令失败"; return 1
  fi
  if in_table "$V"; then
    log "V$V a0_b0 落表 OK ($(awk -F, -v v="$V.0000" 'NR>2 && $1==v && $2=="0.0000" && $3=="0.0000"{print "CY="$10}' "$T0T"))"
    return 0
  fi
  log "V$V post_process 后行仍未出现 — 异常"; return 1
}

apply_recipe() {  # $1=fvSolution: 治愈配方 p/U 0.9→0.5 ((k|omega) 留 0.85)
  local f=$1 bad=0
  sed -i -E 's/^([[:space:]]+p[[:space:]]+)0\.9;$/\10.5;/' "$f"
  sed -i -E 's/^([[:space:]]+U[[:space:]]+)0\.9;$/\10.5;/' "$f"
  grep -qE '^[[:space:]]+p[[:space:]]+0\.5;' "$f" || bad=1
  grep -qE '^[[:space:]]+U[[:space:]]+0\.5;' "$f" || bad=1
  grep -q '0\.9;' "$f" && bad=1
  [ $bad -eq 0 ]
}

upgrade_recipe() {  # $1=fvSolution: r2 升级 (k|omega) 0.85→0.5
  sed -i -E 's/^([[:space:]]+"\(k\|omega\)"[[:space:]]+)0\.85;$/\10.5;/' "$1" \
    && grep -qE '"\(k\|omega\)"[[:space:]]+0\.5;' "$1"
}

clean_case() {  # $1=CASE: 复跑前清时间目录与陈旧 forces (防 latestTime 脏启动)
  find "$1" -maxdepth 1 -type d -regextype posix-extended -regex '.*/[0-9]+' ! -name '0' -exec rm -rf {} +
  rm -f "$1/postProcessing/forces/0/forces.dat" "$1/log.foamRun"
}

judge() {  # $1=V → verdict: OK | FPE | OTHER
  local V=$1 CASE=$ROOT/case_V${V}_a0_b0 s
  s=$(nsteps "$CASE")
  if fped "$CASE"; then echo FPE
  elif [ "$s" -ge 1500 ] 2>/dev/null; then echo OK
  else echo OTHER; fi
}

round2() {  # $1=V: 升级配方复跑 (np=6), 两轮败停手
  local V=$1 CASE=$ROOT/case_V${V}_a0_b0 s
  log "V$V round 2 (升级配方 (k|omega) 0.5, np=6)"
  if ! upgrade_recipe "$CASE/system/fvSolution"; then
    log "V$V r2 配方 sed 失败 — 停手"; return 1; fi
  clean_case "$CASE"
  "$AF/run_solve.sh" "$CASE" 6 1500 >> "$LOG" 2>&1 || true
  s=$(nsteps "$CASE")
  if ! fped "$CASE" && [ "$s" -ge 1500 ] 2>/dev/null; then
    log "V$V r2 求解成功 (1500 步)"; return 0
  fi
  log "V$V r2 仍败 (steps=$s fpe=$(fped "$CASE" && echo Y || echo N)) — 按约定停手回报"
  return 1
}

# ============ Phase 0: V25 重建 + r1 发射 (与 V24 orphan 并行) ============
V25CASE=$ROOT/case_V25_a0_b0
if [ -f "$V25CASE/results.json" ] || in_table 25; then
  log "V25 已完成/已在表 — 跳过重建"
else
  rm -rf "$V25CASE"
  log "V25 残骸已清 (11-13 SIGFPE@89s, np=14 残骸)"
  set +e; set +u
  if   [ -f /opt/openfoam12/etc/bashrc ]; then source /opt/openfoam12/etc/bashrc 2>/dev/null
  elif [ -f "$HOME/OpenFOAM-12/etc/bashrc" ]; then source "$HOME/OpenFOAM-12/etc/bashrc" 2>/dev/null
  elif [ -f /usr/lib/openfoam/openfoam12/etc/bashrc ]; then source /usr/lib/openfoam/openfoam12/etc/bashrc 2>/dev/null
  fi
  set -u
  unset DISPLAY; export HWLOC_COMPONENTS=-gl

  if SURF_LEVEL=5 FIN_LEVEL=7 BOX_LEVEL=3 \
     GEOM_DIR="$AF/cad/v1/cfd_geom_multi_parallel" \
     "$AF/make_case.sh" 25 0 0 "$V25CASE" >> "$LOG" 2>&1; then
    log "V25 make_case OK (S5/F7/B3, GEOM=cfd_geom_multi_parallel)"
  else
    log "V25 make_case FAILED — 停手 (V24 照常看护)"; V25_DEAD=1
  fi

  if [ -z "${V25_DEAD:-}" ]; then
    if ( cd "$V25CASE" && blockMesh > log.blockMesh 2>&1 && snappyHexMesh -overwrite > log.snappy 2>&1 ); then
      log "V25 mesh OK ($(grep 'Finished meshing' "$V25CASE/log.snappy" 2>/dev/null | tail -1))"
    else
      log "V25 MESH FAILED — 看 $V25CASE/log.snappy"; V25_DEAD=1
    fi
  fi

  if [ -z "${V25_DEAD:-}" ]; then
    if apply_recipe "$V25CASE/system/fvSolution"; then
      log "V25 治愈配方已上: p/U 0.5 + (k|omega) 0.85"
    else
      log "V25 配方 sed 校验失败 — 停手"; V25_DEAD=1
    fi
  fi

  if [ -z "${V25_DEAD:-}" ]; then
    ( "$AF/run_solve.sh" "$V25CASE" 6 1500 > "$ROOT/cure_V25_r1.out" 2>&1 ) &
    log "V25 r1 已发射: np=6 endTime=1500 (后台 pid $!)"
  fi
fi

# ============ Phase 1: 双例看护 (V24 orphan + V25 r1) ============
i=0
while running "$ROOT/case_V24_a0_b0" || { [ -z "${V25_DEAD:-}" ] && running "$V25CASE"; }; do
  sleep 120
  i=$((i+1))
  if [ $((i % 5)) -eq 0 ]; then
    log "poll: V24=$(nsteps "$ROOT/case_V24_a0_b0")步 V25=$(nsteps "$V25CASE")步"
  fi
  if [ $i -gt 360 ]; then log "看护超时 12h — 停手回报"; break; fi
done
log "双例 run_solve 均已退出 (V24=$(nsteps "$ROOT/case_V24_a0_b0") V25=$(nsteps "$V25CASE"))"

# ============ Phase 2: 判定 → 成功者先落表 ============
v24v=$(judge 24)
if [ -n "${V25_DEAD:-}" ]; then v25v=DEAD; else v25v=$(judge 25); fi
log "判定: V24=$v24v V25=$v25v"
[ "$v24v" = OK ] && postproc 24
[ "$v25v" = OK ] && postproc 25

# ============ Phase 3: SIGFPE 者升级配方 r2 → 再落表 ============
if [ "$v24v" = FPE ]; then round2 24 && postproc 24; fi
if [ "$v25v" = FPE ]; then round2 25 && postproc 25; fi
[ "$v24v" = OTHER ] && log "V24 非常规退出 (非FPE非满步) — 需人工诊断, 不自动重试"
[ "$v25v" = OTHER ] && log "V25 非常规退出 (非FPE非满步) — 需人工诊断, 不自动重试"

# ============ Phase 4: 终态验证 (546/546 + CY 锚) ============
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
        r = have[k]
        cy = float(r[9])
        print("V%d a0_b0: CL=%s CD=%s Cm=%s CY=%s Cn=%s  |CY|<0.03 锚: %s"
              % (V, r[6], r[7], r[8], r[9], r[11], "PASS" if abs(cy) < 0.03 else "FAIL"))
        try:
            j = json.load(open("/home/qianli/sweep_t0v2/case_V%d_a0_b0/results.json" % V))
            print("V%d results.json: residual_rel=%.4f n_samples=%d" % (V, j["residual_rel"], j["n_samples"]))
        except Exception as e:
            print("V%d results.json 读取失败: %s" % (V, e))
    else:
        print("V%d a0_b0: 未落表" % V)
PY
log "=== 看护流程结束 ==="
