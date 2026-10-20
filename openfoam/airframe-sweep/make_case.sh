#!/usr/bin/env bash
# 生成一个弹体扫气工况 case (从 case_template 实例化)
#   usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]
#   V: 来流速度 m/s; alpha/beta: 攻角/侧滑角 deg (B 系定义, 见 ../README.md)
# 产物: 完整 OpenFOAM v12 case (0/ + constant/ + system/ + triSurface/)
set -euo pipefail

V=${1:?usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]}
ALPHA=${2:?usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]}
BETA=${3:-0}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEST=${4:-"$(pwd)/case_V${V}_a${ALPHA}_b${BETA}"}

RHO=1.225
S_REF=0.017671458676442587    # pi*R^2, R=0.075 (airframe_params.json aero_ref)
COFR=-0.011764705882352946    # 全系统质心 x (airframe_params.json system.com)
I_TURB=${I_TURB:-0.02}        # 来流湍流强度
L_TURB=0.0105                 # 湍流长度尺度 0.07*L_ref

# 来流速度矢量: 空气相对弹体 = -V_B, V_B = V(cos a cos b, sin b, sin a cos b)
read -r UX UY UZ <<<"$(awk -v V="$V" -v a="$ALPHA" -v b="$BETA" 'BEGIN{
  pi=atan2(0,-1); A=a*pi/180; B=b*pi/180;
  printf "%.6f %.6f %.6f", -V*cos(A)*cos(B), -V*sin(B), -V*sin(A)*cos(B) }')"
KVAL=$(awk -v V="$V" -v I="$I_TURB" 'BEGIN{printf "%.6g", 1.5*(I*V)^2}')
OMVAL=$(awk -v k="$KVAL" -v L="$L_TURB" 'BEGIN{printf "%.6g", sqrt(k)/(0.09^0.25*L)}')

mkdir -p "$DEST"
cp -r "$HERE/case_template/." "$DEST/"
mkdir -p "$DEST/constant/triSurface"
cp "$HERE/geometry"/*.stl "$DEST/constant/triSurface/"

# 模板占位替换 (避开 / 干扰, 用 | 分隔)
sed -i "s|__UINF__|$UX $UY $UZ|g" "$DEST/0/U"
sed -i "s|__KVAL__|$KVAL|g; s|__KIN__|$KVAL|g" "$DEST/0/k"
sed -i "s|__OMEGAVAL__|$OMVAL|g; s|__OMEGAIN__|$OMVAL|g" "$DEST/0/omega"
sed -i "s|__COFRX__|$COFR|g" "$DEST/system/controlDict"

cat > "$DEST/CASEINFO" <<EOF
V=$V
alpha=$ALPHA
beta=$BETA
U_inlet=($UX $UY $UZ)
k_inlet=$KVAL
omega_inlet=$OMVAL
rho=$RHO
S_ref=$S_REF
L_ref=0.15
CofR=$COFR
EOF

echo "case -> $DEST"
echo "  U_inlet = ($UX, $UY, $UZ)  |U| = $(awk -v x="$UX" -v y="$UY" -v z="$UZ" 'BEGIN{printf "%.4f", sqrt(x*x+y*y+z*z)}')"
echo "  k=$KVAL omega=$OMVAL"
