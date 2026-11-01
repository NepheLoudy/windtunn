#!/usr/bin/env bash
# T2 GPU 队列 v1 (11-01) — 把 CPU 空窗排满: 分支矩阵/种子统计/Re 阶梯/分辨率收敛
# 坑防线: 无 pkill; setsid 分离; 断点续跑(末行 t==STEPS 才跳过); P0 回归门 ±3%;
#         体素观测(SOLID_COM); 与 CPU sweep 共存(内存/显存预算见 gpu_plan_1101.md)
set -u
# 防重入锁: mkdir 原子锁 (pgrep -cf 会把 $() 子 shell 的继承 cmdline 也算进去, 永远自锁 — 11-01)
LOCK=/tmp/t2_queue.lock
if ! mkdir "$LOCK" 2>/dev/null; then echo "queue-already-running (lock $LOCK)"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
BIN=~/fluidx3d_v3/FluidX3D-master/bin
SUM="$BIN/out/t2_queue_summary.csv"
QLOG="$BIN/t2_queue.log"

[ -f "$SUM" ] || echo "tag,alpha,beta,nx,seed,nu,V,steps,fx,fy,fz" >> "$SUM"

run_case() { # tag alpha beta nx nu V seed steps
  local tag=$1 a=$2 b=$3 nx=$4 nu=$5 v=$6 seed=$7 steps=$8
  local f="$BIN/out/forces_${tag}.csv"
  if [ -f "$f" ] && [ "$(tail -1 "$f" | cut -d, -f1)" = "$steps" ]; then
    echo "[skip] $tag (done)"; return 0
  fi
  echo "[$(date +%m-%d\ %H:%M)] run $tag a=$a b=$b nx=$nx nu=$nu V=$v seed=$seed steps=$steps"
  GEOM_DIR=cfd_v4parts/ ALPHA=$a BETA=$b NX=$nx NU=$nu V_LBM=$v SEED=$seed STEPS=$steps TAG=_$tag \
    "$BIN/FluidX3D" >> "$QLOG" 2>&1
  local fx fy fz
  read -r fx fy fz <<<"$(tail -20 "$f" | awk -F, 'NR>0 && $1!="t" {sfx+=$2; sfy+=$3; sfz+=$4; n++} END{printf "%.4f %.4f %.4f", sfx/n, sfy/n, sfz/n}')"
  echo "${tag},${a},${b},${nx},${seed},${nu},${v},${steps},${fx},${fy},${fz}" >> "$SUM"
  echo "    -> fx=$fx fy=$fy fz=$fz"
}

# ---------- P0 回归门 (真实性: 与 11-01 已验证结果对齐 ±3%) ----------
run_case gate 12.5 0 220 0.01 0.05 0 30000
GATE_FX=$(tail -20 "$BIN/out/forces_gate.csv" | awk -F, '$1!="t"{s+=$2;n++} END{printf "%.4f", s/n}')
OK=$(awk -v x="$GATE_FX" 'BEGIN{print (x<-36.4 && x>-38.7)?1:0}')
if [ "$OK" != "1" ]; then echo "P0 GATE FAIL fx=$GATE_FX (expect -37.53±3%) — queue aborted"; exit 42; fi
echo "P0 gate PASS fx=$GATE_FX"

# ---------- P1 粗格分支矩阵 (α6 × β11 = 66, 12 例已有自动跳过) ----------
for A in 10 -10 12.5 -12.5 15 -15; do
  for B in 0 1.25 -1.25 2.5 -2.5 5 -5 7.5 -7.5 10 -10; do
    run_case "c_a${A}_b${B}" "$A" "$B" 220 0.01 0.05 0 300000
  done
done

# ---------- P2 粗格种子统计 (分支不确定性, 4 条件 × 8 种子) ----------
for A in 12.5 -12.5 15 -15; do
  for S in 1 2 3 4 5 6 7 8; do
    run_case "s_a${A}_seed${S}" "$A" 0 220 0.01 0.05 "$S" 300000
  done
done

# ---------- P3 Re 阶梯 (V 扫描, FVM 跨V<1% 的 LBM 交叉验证) ----------
for V in 0.025 0.075; do
  run_case "re_v${V}_a12.5" 12.5 0 220 0.01 "$V" 0 300000
  run_case "re_v${V}_a-15" -15 0 220 0.01 "$V" 0 300000
done

# ---------- P4 中格 330 收敛验证 (Re 匹配: nu×1.5) ----------
for C in "12.5 0" "-15 0" "12.5 5"; do
  set -- $C; run_case "m330_a$1_b$2" "$1" "$2" 330 0.015 0.05 0 300000
done

# ---------- P5 细格 440 收敛验证 (nu×2) ----------
for C in "12.5 0" "-15 0" "12.5 5"; do
  set -- $C; run_case "f440_a$1_b$2" "$1" "$2" 440 0.02 0.05 0 300000
done

# ---------- P6 细格分支矩阵 (主产出, ~38h) ----------
for A in 10 -10 12.5 -12.5 15 -15; do
  for B in 0 2.5 -2.5 5 -5 7.5 -7.5 10 -10; do
    run_case "f_a${A}_b${B}" "$A" "$B" 440 0.02 0.05 0 300000
  done
done

# ---------- P7 细格种子统计 (~19h) ----------
for A in 12.5 -12.5 15 -15; do
  for S in 1 2 3 4 5 6 7 8; do
    run_case "fs_a${A}_seed${S}" "$A" 0 440 0.02 0.05 "$S" 300000
  done
done

# ---------- P8 细格大侧滑角点 ----------
for C in "15 15" "15 -15" "-15 15" "-15 -15"; do
  set -- $C; run_case "f_a$1_b$2" "$1" "$2" 440 0.02 0.05 0 300000
done

# ---------- P9 超细 660 锚点 (nu×3, 显存 ~4GB) ----------
run_case "u660_a12.5_b0" 12.5 0 660 0.03 0.05 0 300000
run_case "u660_a-15_b0" -15 0 660 0.03 0.05 0 300000

echo "=== T2 queue ALL DONE $(date) — summary: $SUM ==="
