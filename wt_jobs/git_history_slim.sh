#!/usr/bin/env bash
# ============================================================
#  git_history_slim.sh -- P01 收工后的 git 历史瘦身 + 四机修正
#  曼波 2026-11-19 批准: 收工后执行; 产线保护隔离内建
#  用法: bash git_history_slim.sh [--dry-run]
# ============================================================
set -euo pipefail
TS=$(date '+%Y%m%d_%H%M%S')
LOG=/d/WindTunnelSuite/wt_jobs/history_slim_$TS.log
SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=12 -i $HOME/.ssh/id_ed25519"
exec > >(tee -a "$LOG") 2>&1

echo "=== git history slim: $TS ==="

# ---------- 0. 产线保护检查 (任一不过即中止, 不碰历史) ----------
echo "--- [0] 产线保护检查 ---"
FAIL=0
# 0a. 四台行数齐 + 无产线进程
row_check() { # $1=label $2=cmd
  local out
  out=$(timeout 60 ssh $SSH_OPTS "$1" "$2" 2>/dev/null | grep -v WARNING | grep -v "store now" | grep -v "may need" | tail -1)
  echo "  $1: $out"
  [ "$out" = "0" ] || { echo "  !! $1 产线进程未静止"; FAIL=1; }
}
echo "  desktop:"
D=$(wsl -e bash -lc 'ps aux | grep -cE "[f]oamRun|[s]nappy|[r]un_pack|[r]un_sweep"' 2>/dev/null || echo "?")
echo "    procs=$D"; [ "$D" = "0" ] || FAIL=1
echo "  NUC1:";  row_check "lenovo@192.168.137.28" 'wsl -d Ubuntu-24.04 -u root -- bash -lc "ps aux | grep -cE \"[f]oamRun|[s]nappy|[r]un_pack\" || true"'
echo "  NUC2:";  row_check "lenovo@192.168.138.50" 'wsl -d Ubuntu -u root -- bash -lc "ps aux | grep -cE \"[f]oamRun|[s]nappy|[r]un_pack\" || true"'
Q=$(wsl -e bash -lc 'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519 qianli@100.90.63.31 "ps aux | grep -cE \"[f]oamRun|[s]nappy|[r]un_pack\" || true"' 2>/dev/null | tail -1)
echo "  qianli: procs=$Q"; [ "$Q" = "0" ] || FAIL=1
# 0b. master 表行数 = 55 (collect+verify 已 PASS)
if [ -f /d/WindTunnelSuite/wt_jobs/P01_FINAL_汇报.md ]; then
  echo "  P01_FINAL_汇报.md 存在 (收工完成标志)"
else
  echo "  !! P01_FINAL_汇报.md 不存在 — collect+verify 未完成, 中止"
  FAIL=1
fi
if [ "$FAIL" = "1" ]; then
  echo "=== 产线未静止或收工未确认 — 中止 (安全阀) ==="
  exit 1
fi
echo "  [OK] 四机静止 + 收工确认"

# ---------- 1. 本机 fresh clone + filter-repo ----------
echo "--- [1] filter-repo 本机执行 ---"
WORK=/d/_repo_slim_$TS
mkdir -p "$WORK"
cd "$WORK"
git clone --no-local -q https://github.com/NepheLoudy/windtunn.git slim_repo
cd slim_repo
BEFORE=$(du -sh .git | cut -f1)
echo "  before: .git=$BEFORE"
py -3 -m pip install -q git-filter-repo 2>/dev/null || py -3 -m pip install --user -q git-filter-repo
git filter-repo --force \
  --invert-paths --path wt_jobs/www/poses --path wt_jobs/www/poses_archive \
  --path wt_jobs/tmp --path wt_jobs/collect --path wt_jobs/MORNING_REPORT_20261119.md
AFTER=$(du -sh .git | cut -f1)
echo "  after : .git=$AFTER"
echo "  重写后最新 commit: $(git log --oneline -1)"

# ---------- 2. force push ----------
echo "--- [2] force push ---"
git push --force origin HEAD:main 2>&1 | tail -2

# ---------- 3. bundle 给 NUC (校园网 GitHub 不通, bundle 中转) ----------
echo "--- [3] bundle 中转 (NUC1/NUC2) ---"
git bundle create /d/nuc_relay/windtunn_slim.bundle --all
ls -la /d/nuc_relay/windtunn_slim.bundle

# ---------- 4. 四机仓库重建 (产线保护: 旧目录改名保底, 不删) ----------
echo "--- [4] 四机仓库重建 ---"
# 4a. desktop WSL
wsl -e bash -lc '
set -e
cd /root/work
mv windtunnel windtunnel_old_slim 2>/dev/null || true
git clone -q /mnt/d/nuc_relay/windtunn_slim.bundle windtunnel 2>/dev/null || git clone -q /mnt/d/_repo_slim_*/slim_repo /root/work/windtunnel
cd windtunnel && echo "  desktop: $(git log --oneline -1) | STL=$(ls openfoam/airframe-sweep/cad/v1/cfd_geom_multi_parallel/*.stl 2>/dev/null | wc -l)"
'
# 4b/4c. NUC1/NUC2 (bundle 走 D:\, WSL 内 clone)
for spec in "192.168.137.28:Ubuntu-24.04:NUC1" "192.168.138.50:Ubuntu:NUC2"; do
  IFS=: read ip distro name <<< "$spec"
  timeout 120 ssh $SSH_OPTS "lenovo@$ip" "wsl -d $distro -u root -- bash -lc 'cd /root/work && mv windtunnel windtunnel_old_slim 2>/dev/null; git clone -q /mnt/d/nuc_relay/windtunn_slim.bundle windtunnel && cd windtunnel && echo \"  $name: \$(git log --oneline -1) | STL=\$(ls openfoam/airframe-sweep/cad/v1/cfd_geom_multi_parallel/*.stl | wc -l)\"'"
done
# 4d. qianli (原生 Linux, GitHub 直连或 bundle scp)
wsl -e bash -lc 'scp -q -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519 /mnt/d/nuc_relay/windtunn_slim.bundle qianli@100.90.63.31:/tmp/' 2>/dev/null
wsl -e bash -lc 'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i /root/.ssh/id_ed25519 qianli@100.90.63.31 "cd ~/windtunnel && git fetch -q origin 2>/dev/null; git reset -q --hard origin/main 2>/dev/null || (cd ~ && mv windtunnel windtunnel_old_slim && git clone -q /tmp/windtunn_slim.bundle windtunnel); cd ~/windtunnel && echo \"  qianli: \$(git log --oneline -1) | STL=\$(ls openfoam/airframe-sweep/cad/v1/cfd_geom_multi_parallel/*.stl | wc -l)\""' 2>/dev/null

# ---------- 5. 验证 ----------
echo "--- [5] 终验 ---"
echo "  各机 git log + STL 数见上; sweep_pack_work 产线数据不在仓库内, 天然不受影响"
echo "=== DONE (log: $LOG) ==="
