#!/usr/bin/env bash
# 克隆已建网格的 case, 只改来流边界 (V 扫描复用网格 — blockMesh/snappy 只跑一次)
#   usage: clone_case.sh <src_case> <dst_case> <V_m/s>
#   环境: WARM_FROM=<已收敛同组 case>  热启动场源 (可选; 空=冷启动, 从 SRC 复制 0/)
#         — mesh 恒从 SRC 复用; 热启动只换「初始场」, 稳态解唯一故不改变答案 (只改收敛路径)
#         WARM_MIN_RESID=<热启动源收敛门槛> (默认 0.3, residual_rel 上限)
#         I_TURB=<湍流入流强度> (默认 0.02)
#   alpha/beta 从 src 的 CASEINFO 继承 (同一几何组)
#   替换机制: 按场源 CASEINFO 记录的旧 U/k/omega 数值 → 新 V 数值 (占位符已被消费, 不可依赖)
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=${1:?usage: clone_case.sh <src> <dst> <V>}
DST=${2:?usage: clone_case.sh <src> <dst> <V>}
V=${3:?usage: clone_case.sh <src> <dst> <V>}
I_TURB=${I_TURB:-0.02}
WARM_FROM=${WARM_FROM:-}
WARM_MIN_RESID=${WARM_MIN_RESID:-0.3}   # 热启动源收敛门槛 (residual_rel 上限)

[ -d "$SRC/constant/polyMesh" ] || { echo "src 无网格: $SRC"; exit 1; }
[ -f "$DST/constant/polyMesh/points" ] && { echo "dst 已存在网格, 跳过: $DST"; exit 0; }

# --- 热启动源筛选: 五重安全阀, 任一不过即退回冷启动 (SRC) ---
FIELD_SRC="$SRC"
WARM_TIME=""    # 非空 = 采用该时间目录的收敛场 (set -u 安全: 冷启动路径下为默认)
if [ -n "$WARM_FROM" ]; then
  warm_ok=1; warm_why=""
  [ -d "$WARM_FROM/0" ] || { warm_ok=0; warm_why="无 0/ 目录"; }
  if [ "$warm_ok" = 1 ] && [ ! -f "$WARM_FROM/results.json" ]; then
    warm_ok=0; warm_why="无 results.json (未跑完)"
  fi
  if [ "$warm_ok" = 1 ]; then
    rr=$(python3 -c "import json,sys
try:
    d=json.load(open(sys.argv[1]))
    print(abs(float(d.get('residual_rel') or 0.0)))
except Exception:
    print(1.0)" "$WARM_FROM/results.json" 2>/dev/null || echo 1.0)
    awk -v r="$rr" -v lim="$WARM_MIN_RESID" 'BEGIN{exit !(r<=lim)}' || {
      warm_ok=0; warm_why="residual_rel=$rr > $WARM_MIN_RESID (振荡/未收敛)"; }
  fi
  # 姿态一致性: 场源必须与 SRC 同 (alpha,beta) —— 否则 mesh 与场不匹配
  if [ "$warm_ok" = 1 ]; then
    sab=$(awk -F= '/^alpha=/{a=$2}/^beta=/{b=$2}END{print a+0"_"b+0}' "$SRC/CASEINFO")
    wab=$(awk -F= '/^alpha=/{a=$2}/^beta=/{b=$2}END{print a+0"_"b+0}' "$WARM_FROM/CASEINFO" 2>/dev/null || echo "x")
    [ "$sab" = "$wab" ] || { warm_ok=0; warm_why="姿态不匹配 ($wab vs $sab)"; }
  fi
  # 场文件齐备: 收敛场在**最后一个时间目录**(不在 0/ — 0/ 恒为初始场), 五场都要在
  WARM_TIME=""
  if [ "$warm_ok" = 1 ]; then
    WARM_TIME=$(cd "$WARM_FROM" && ls -d [0-9]* 2>/dev/null | grep -E '^[0-9]+$' | grep -vx '0' | sort -n | tail -1)
    [ -n "$WARM_TIME" ] || { warm_ok=0; warm_why="无收敛时间目录(只有 0/)"; }
  fi
  if [ "$warm_ok" = 1 ]; then
    for f in U k omega p nut; do
      [ -f "$WARM_FROM/$WARM_TIME/$f" ] || { warm_ok=0; warm_why="场文件缺 $WARM_TIME/$f"; break; }
    done
  fi
  if [ "$warm_ok" = 1 ]; then
    FIELD_SRC="$WARM_FROM"
    echo "  warm-start: 场源=$(basename "$WARM_FROM")@$WARM_TIME (mesh 仍复用 $(basename "$SRC"))"
  else
    echo "  warm-start 跳过 -> 冷启动 (原因: $warm_why)"
  fi
fi

# 从场源 CASEINFO 继承 alpha/beta/L_turb (新版按 patch 改写, 不再需要旧边界数值)
read -r ALPHA BETA V_OLD L_TURB <<<"$(awk -F= '
  /^alpha=/{a=$2}/^beta=/{b=$2}/^L_turb=/{l=$2}/^V=/{v=$2}
  END{print a+0, b+0, v+0, l}' "$FIELD_SRC/CASEINFO")"
L_TURB=${L_TURB:-0.0105}

read -r UX UY UZ KVAL OMVAL <<<"$(awk -v V="$V" -v A="$ALPHA" -v B="$BETA" -v I="$I_TURB" -v L="$L_TURB" 'BEGIN{
  pi=atan2(0,-1); ar=A*pi/180; br=B*pi/180;
  k=1.5*(I*V)^2;
  printf "%.6f %.6f %.6f %.6g %.6g", -V*cos(ar)*cos(br), -V*sin(br), -V*sin(ar)*cos(br),
  k, sqrt(k)/(0.09^0.25*L) }')"

mkdir -p "$DST"
cp -r "$SRC"/constant "$DST"/
cp -r "$SRC"/system "$DST"/
cp -r "$FIELD_SRC"/0 "$DST"/0

# 热启动: 用收敛时间目录的场覆盖 0/ (0/ 恒为初始场, 收敛解在最后时间目录)
if [ -n "$WARM_TIME" ]; then
  for f in U k omega p nut; do
    cp "$FIELD_SRC/$WARM_TIME/$f" "$DST/0/$f"
  done
fi

# 数值替换: 按 patch 名精确改写 (inlet/outlet/side 的 uniform 项)
# 不用旧值字符串 sed — 热启动场取自收敛时间目录, 写盘是紧凑格式(-19.9239 0 -1.74311),
# 与模板 6 位小数格式不同会静默失配 (2026-11-18 实测); 且 nonuniform 内部场百万数值
# 用裸字符串替换有巧合命中风险。
python3 "$HERE/rewrite_inlet_bc.py" "$DST/0/U" U "$UX" "$UY" "$UZ" > /dev/null || {
  echo "边界改写失败 (U): $DST/0/U"; exit 1; }
python3 "$HERE/rewrite_inlet_bc.py" "$DST/0/k" scalar "$KVAL" > /dev/null || {
  echo "边界改写失败 (k): $DST/0/k"; exit 1; }
python3 "$HERE/rewrite_inlet_bc.py" "$DST/0/omega" scalar "$OMVAL" > /dev/null || {
  echo "边界改写失败 (omega): $DST/0/omega"; exit 1; }

# 校验 (数值比较, 避免 grep 把负数当选项): 0/U 首个 uniform() 三分量须等于新 U
awk -v ex="$UX" -v ey="$UY" -v ez="$UZ" '
  /uniform *\(/ && !done {
    s=$0; sub(/.*uniform *\(/,"",s); sub(/\).*/,"",s); n=split(s,t," ");
    if (n>=3) { done=1; if ((t[1]-ex)^2+(t[2]-ey)^2+(t[3]-ez)^2 > 1e-8) { print "MISMATCH"; exit 1 } }
  }
  END { if (!done) { print "NOFIELD"; exit 1 } }' "$DST/0/U" > /dev/null || {
  echo "替换校验失败 (U 未按新 V 改写): $DST/0/U"; exit 1; }

awk -v V="$V" -v ux="$UX" -v uy="$UY" -v uz="$UZ" -v k="$KVAL" -v om="$OMVAL" '
  /^V=/         { print "V=" V; next }
  /^U_inlet=/   { print "U_inlet=(" ux " " uy " " uz ")"; next }
  /^k_inlet=/   { print "k_inlet=" k; next }
  /^omega_inlet=/{ print "omega_inlet=" om; next }
  { print }' "$SRC/CASEINFO" > "$DST/CASEINFO"

echo "cloned (mesh reused, boundary revalued): $DST  V=$V (alpha=$ALPHA beta=$BETA)"
