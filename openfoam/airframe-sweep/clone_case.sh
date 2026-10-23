#!/usr/bin/env bash
# 克隆已建网格的 case, 只改来流边界 (V 扫描复用网格 — blockMesh/snappy 只跑一次)
#   usage: clone_case.sh <src_case> <dst_case> <V_m/s>
#   alpha/beta 从 src 的 CASEINFO 继承 (同一几何组)
set -euo pipefail

SRC=${1:?usage: clone_case.sh <src> <dst> <V>}
DST=${2:?usage: clone_case.sh <src> <dst> <V>}
V=${3:?usage: clone_case.sh <src> <dst> <V>}
I_TURB=${I_TURB:-0.02}

[ -d "$SRC/constant/polyMesh" ] || { echo "src 无网格: $SRC"; exit 1; }
[ -f "$DST/constant/polyMesh/points" ] && { echo "dst 已存在网格, 跳过: $DST"; exit 0; }

read -r ALPHA BETA L_TURB_IN <<<"$(awk -F= '/^alpha=/{a=$2}/^beta=/{b=$2}/^L_turb=/{l=$2}END{print a+0, b+0, l}' "$SRC/CASEINFO")"
L_TURB=${L_TURB_IN:-0.0105}
read -r UX UY UZ KVAL OMVAL <<<"$(awk -v V="$V" -v A="$ALPHA" -v B="$BETA" -v I="$I_TURB" -v L="$L_TURB" 'BEGIN{
  pi=atan2(0,-1); ar=A*pi/180; br=B*pi/180;
  k=1.5*(I*V)^2;
  printf "%.6f %.6f %.6f %.6g %.6g", -V*cos(ar)*cos(br), -V*sin(br), -V*sin(ar)*cos(br),
  k, sqrt(k)/(0.09^0.25*L) }')"

mkdir -p "$DST"
cp -r "$SRC"/constant "$DST"/
cp -r "$SRC"/system "$DST"/
cp -r "$SRC"/0 "$DST"/0
[ -d "$SRC/postProcessing" ] && cp -r "$SRC"/postProcessing "$DST"/ 2>/dev/null || true

sed -i "s|__UINF__|$UX $UY $UZ|g" "$DST/0/U"
sed -i "s|__KVAL__|$KVAL|g; s|__KIN__|$KVAL|g" "$DST/0/k"
sed -i "s|__OMEGAVAL__|$OMVAL|g; s|__OMEGAIN__|$OMVAL|g" "$DST/0/omega"

awk -v V="$V" -v ux="$UX" -v uy="$UY" -v uz="$UZ" -v k="$KVAL" -v om="$OMVAL" '
  /^V=/         { print "V=" V; next }
  /^U_inlet=/   { print "U_inlet=(" ux " " uy " " uz ")"; next }
  /^k_inlet=/   { print "k_inlet=" k; next }
  /^omega_inlet=/{ print "omega_inlet=" om; next }
  { print }' "$SRC/CASEINFO" > "$DST/CASEINFO"

echo "cloned (mesh reused): $DST  V=$V (alpha=$ALPHA beta=$BETA)"
