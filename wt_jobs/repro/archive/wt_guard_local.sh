#!/usr/bin/env bash
# =============================================================================
# wt_guard_local.sh — qianli 本地哨兵 (2026-11-18 自桌面 schtasks WT_qianli_guard 迁入)
# 背景: 桌面 guard 11-15 09:00 最后一次运行后停用, qianli 11-12/11-13 重启后无人兜底;
#       自愈责任迁回本机, 不再依赖桌面在线。桌面侧 guard 保留为备用 (DISABLE 维持)。
# 触发: crontab @reboot + */10 (每轮一次探活; flock 防重叠, 上一轮没跑完自动让位)
# 四字段: runner(run_sweep_v2) / chain(chain_t1_v3) / reaper(sweep_t1) / GPU(run+queue)
#
# 动作矩阵 (桌面 qianli_guard.py 规则 + 发车 env 自检, t1_r3_1117 先例):
#   reaper_t1 缺        → 重拉 case_reaper.sh sweep_t1 600
#   eng=0 & chain=0     → env 自检 (source ~/OpenFOAM-12/etc/bashrc + command -v
#                         blockMesh/snappyHexMesh/foamRun) 通过才直接发车 T1 引擎;
#                         自检失败宁可不拉, 记 CRITICAL (11-17 裸环境 546 败教训)
#   eng=1 & chain=0     → 重拉 chain_t1_v3.sh 作哨兵 (引擎死后的补跑由它按表判重接管)
#   eng=0 & chain=1     → 不抢 (chain 自身 600s 轮询会拉, 双拉会撞引擎)
#   gpu_run=0 & gpu_queue=0 & $HOME 有 tN_queue.sh → 拉最新队列脚本 (队列自带原子锁)
#
# 铁律: 永不调用 launch_t0v2.sh — rm -rf 全清启动器, 中途调用删光已完成工况。
# 暂停: touch ~/.wt_guard_pause 后空转 (人工调试期防拉回), rm 后恢复。
# 日志: ~/wt_guard_local.log (>1MB 轮转 .old)
# =============================================================================
exec 9>"$HOME/.wt_guard_local.lock"
flock -n 9 || exit 0

LOG="$HOME/wt_guard_local.log"
[ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 1048576 ] && mv "$LOG" "$LOG.old"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

OF_BASHRC="$HOME/OpenFOAM-12/etc/bashrc"
AF="$HOME/windtunnel/openfoam/airframe-sweep"
GPU_LOG="$HOME/fluidx3d_v3/FluidX3D-master/bin/gpu_queue_relaunch.log"

# ---- 探活 (模式串字符类断自匹配, 防 pgrep 撞自己; 严禁单引号包模式) ----
pgrep -cf "run_sweep_v[2]"  >/dev/null && eng=1    || eng=0
pgrep -cf "chain_t1_v[3]"   >/dev/null && chain=1  || chain=0
reaper_t1=$(pgrep -af "case_reape[r].sh" | grep -q sweep_t1 && echo 1 || echo 0)
pgrep -cf "FluidX3[D]"      >/dev/null && gpu_run=1   || gpu_run=0
pgrep -cf "t[0-9_]*_queue.s[h]" >/dev/null && gpu_queue=1 || gpu_queue=0
gpu_next=$(ls "$HOME" 2>/dev/null | grep "^t[0-9_]*_queue\.sh$" | sort | tail -1)

if [ -f "$HOME/.wt_guard_pause" ]; then
  log "PAUSE eng=$eng chain=$chain reaper=$reaper_t1 gpu=$gpu_run/$gpu_queue — .wt_guard_pause 在, 空转"
  exit 0
fi
log "probe eng=$eng chain=$chain reaper_t1=$reaper_t1 gpu_run=$gpu_run gpu_queue=$gpu_queue next=${gpu_next:-none}"

acted=0

# 1) 收割机 (T1 已开跑, 只管 sweep_t1 这台)
if [ "$reaper_t1" = 0 ]; then
  # 9>&-: 拉起的长命子进程必须关掉锁 FD, 否则它们继承 flock 把哨兵自己锁死在门外
  setsid nohup bash "$HOME/case_reaper.sh" "$HOME/sweep_t1" 600 \
    >> "$HOME/sweep_t1/reaper.log" 2>&1 < /dev/null 9>&- &
  sleep 1
  log "ACTION relaunch reaper_t1 alive=$(pgrep -af 'case_reape[r].sh' | grep -c sweep_t1)"
  acted=1
fi

# 2) 引擎直接发车 — 仅 chain 也不在时 (防双引擎); env 自检不过宁可不拉
if [ "$eng" = 0 ] && [ "$chain" = 0 ]; then
  envok=0
  if [ -f "$OF_BASHRC" ]; then
    if ( source "$OF_BASHRC" 2>/dev/null
         command -v blockMesh    >/dev/null
         command -v snappyHexMesh >/dev/null
         command -v foamRun      >/dev/null ); then envok=1; fi
  fi
  if [ "$envok" = 1 ]; then
    (
      exec 9>&-
      source "$OF_BASHRC"
      unset DISPLAY; export HWLOC_COMPONENTS=-gl
      cd "$AF" || exit 1
      export OUT_CSV="$HOME/sweep_t1/t1_table.csv"
      export SWEEP_V="20 21 22 23 24 25"
      export SWEEP_ALPHA="-15 -12.5 -10 -7.5 -5 -2.5 0 2.5 5 7.5 10 12.5 15"
      export SWEEP_BETA="-15 -10 -5 0 5 10 15"
      export SURF_LEVEL=6 FIN_LEVEL=8 BOX_LEVEL=3
      export GEOM_DIR="$PWD/cad/v1/cfd_geom_multi_parallel"
      setsid nohup ./run_sweep_v2.sh "$HOME/sweep_t1" 14 \
        >> "$HOME/sweep_t1/sweep.log" 2>&1 < /dev/null &
    )
    sleep 2
    pgrep -cf "run_sweep_v[2]" >/dev/null && a=1 || a=0
    log "ACTION relaunch engine(t1, L6/L8 np=14) alive=$a"
    acted=1
  else
    log "CRITICAL engine 缺失且 env 自检失败 ($OF_BASHRC / blockMesh/snappy/foamRun 不全) — 不发车, 需人工"
  fi
fi

# 3) chain 哨兵 — 引擎活着而 chain 缺时拉回 (引擎缺时不抢, 见 2)
if [ "$eng" = 1 ] && [ "$chain" = 0 ]; then
  setsid nohup bash "$HOME/chain_t1_v3.sh" >> "$HOME/chain_v3_local.log" 2>&1 < /dev/null 9>&- &
  sleep 1
  pgrep -cf "chain_t1_v[3]" >/dev/null && a=1 || a=0
  log "ACTION relaunch chain(sentinel) alive=$a"
  acted=1
fi
if [ "$eng" = 0 ] && [ "$chain" = 1 ]; then
  log "note: engine 缺而 chain 在 — chain 600s 轮询自己接管, 不抢"
fi

# 4) GPU 队列接续 (桌面 E1 规则; 队列自带断点续跑+原子锁, 拉重安全)
if [ "$gpu_run" = 0 ] && [ "$gpu_queue" = 0 ] && [ -n "$gpu_next" ]; then
  setsid nohup bash "$HOME/$gpu_next" >> "$GPU_LOG" 2>&1 < /dev/null 9>&- &
  sleep 2
  pgrep -cf "FluidX3[D]" >/dev/null && a=1 || a=0
  log "ACTION relaunch gpu_queue:$gpu_next gpu_alive=$a"
  acted=1
fi

[ "$acted" = 0 ] && log "ok — 四字段齐全, 无需动作"
exit 0
