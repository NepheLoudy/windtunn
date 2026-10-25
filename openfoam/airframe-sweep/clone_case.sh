#!/usr/bin/env bash
# 克隆已建网格的 case, 只改来流边界 (V 扫描复用网格 — blockMesh/snappy 只跑一次)
#   usage: clone_case.sh <src_case> <dst_case> <V_m/s>
#   alpha/beta 从 src 的 CASEINFO 继承 (同一几何组)
#   替换机制: 按 SRC/CASEINFO 记录的旧 U/k/omega 数值 → 新 V 数值 (占位符在 src 已被消费, 不可依赖)
set -euo pipefail

SRC=${1:?usage: clone_case.sh <src> <dst> <V>}
DST=${2:?usage: clone_case.sh <src> <dst> <V>}
V=${3:?usage: clone_case.sh <src> <dst> <V>}
I_TURB=${I_TURB:-0.02}

[ -d "$SRC/constant/polyMesh" ] || { echo "src 无网格: $SRC"; exit 1; }
[ -f "$DST/constant/polyMesh/points" ] && { echo "dst 已存在网格, 跳过: $DST"; exit 0; }

# 从 SRC/CASEINFO 继承 alpha/beta/L_turb 和旧边界数值 (U 三分量在 awk 内拆开, 避免 read 空格挤位)
read -r ALPHA BETA V_OLD U1_OLD U2_OLD U3_OLD K_OLD OM_OLD L_TURB <<<"$(awk -F= '
  /^alpha=/{a=$2}/^beta=/{b=$2}/^L_turb=/{l=$2}
  /^V=/{v=$2}
  /^U_inlet=/{u=$2}/^k_inlet=/{k=$2}/^omega_inlet=/{o=$2}
  END{gsub(/\(|\)/,"",u); split(u,t," "); print a+0, b+0, v+0, t[1], t[2], t[3], k, o, l}' "$SRC/CASEINFO")"
L_TURB=${L_TURB:-0.0105}
[ -n "$U1_OLD" ] || { echo "src CASEINFO 缺 U_inlet 记录: $SRC"; exit 1; }

read -r UX UY UZ KVAL OMVAL <<<"$(awk -v V="$V" -v A="$ALPHA" -v B="$BETA" -v I="$I_TURB" -v L="$L_TURB" 'BEGIN{
  pi=atan2(0,-1); ar=A*pi/180; br=B*pi/180;
  k=1.5*(I*V)^2;
  printf "%.6f %.6f %.6f %.6g %.6g", -V*cos(ar)*cos(br), -V*sin(br), -V*sin(ar)*cos(br),
  k, sqrt(k)/(0.09^0.25*L) }')"

mkdir -p "$DST"
cp -r "$SRC"/constant "$DST"/
cp -r "$SRC"/system "$DST"/
cp -r "$SRC"/0 "$DST"/0

# 数值替换: 旧 U 矢量三分量逐个换 (新值含负号, 用 | 分隔)
sed -i "s|$U1_OLD $U2_OLD $U3_OLD|$UX $UY $UZ|g" "$DST/0/U"
sed -i "s|$K_OLD|$KVAL|g" "$DST/0/k"
sed -i "s|$OM_OLD|$OMVAL|g" "$DST/0/omega"

# 校验: 新 U 必须出现, 旧 U 不得残留
if ! grep -q "$UX $UY $UZ" "$DST/0/U" || grep -q "$U1_OLD $U2_OLD $U3_OLD" "$DST/0/U"; then
  echo "替换校验失败: $DST/0/U"; exit 1
fi

awk -v V="$V" -v ux="$UX" -v uy="$UY" -v uz="$UZ" -v k="$KVAL" -v om="$OMVAL" '
  /^V=/         { print "V=" V; next }
  /^U_inlet=/   { print "U_inlet=(" ux " " uy " " uz ")"; next }
  /^k_inlet=/   { print "k_inlet=" k; next }
  /^omega_inlet=/{ print "omega_inlet=" om; next }
  { print }' "$SRC/CASEINFO" > "$DST/CASEINFO"

echo "cloned (mesh reused, boundary revalued): $DST  V=$V (alpha=$ALPHA beta=$BETA)"
