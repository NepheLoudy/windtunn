#!/usr/bin/env bash
# 生成一个弹体扫气工况 case (从 case_template 实例化)
#   usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]
#   环境变量: GEOM_DIR=<含 *.stl 的目录>  (默认 ../geometry)
#             SURF_LEVEL=<壁面细化级>     (默认 4)
#             BOX_LEVEL=<近体盒细化级>    (默认 3)
#   V: 来流速度 m/s; alpha/beta: 攻角/侧滑角 deg (B 系定义)
set -euo pipefail

V=${1:?usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]}
ALPHA=${2:?usage: make_case.sh <V> <alpha_deg> [beta_deg] [dest_dir]}
BETA=${3:-0}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEST=${4:-"$(pwd)/case_V${V}_a${ALPHA}_b${BETA}"}
GEOM=${GEOM_DIR:-"$HERE/geometry"}
SURF_LEVEL=${SURF_LEVEL:-4}
FIN_LEVEL=${FIN_LEVEL:-$SURF_LEVEL}
BOX_LEVEL=${BOX_LEVEL:-3}

RHO=1.225
I_TURB=${I_TURB:-0.02}

[ -d "$GEOM" ] || { echo "GEOM_DIR 不存在: $GEOM"; exit 1; }
STLS=$(cd "$GEOM" && ls *.stl 2>/dev/null || true)
[ -n "$STLS" ] || { echo "$GEOM 下没有 .stl"; exit 1; }

# ---- 几何包围盒 (m) ----
read -r X0 Y0 Z0 X1 Y1 Z1 <<<"$(cd "$GEOM" && python3 - <<'PY'
import struct, glob, os
lo=[1e9]*3; hi=[-1e9]*3
for f in glob.glob('*.stl'):
    d=open(f,'rb').read()
    if d[:5].lower()==b'solid' and b'facet' in d[:400]:
        vs=[l.split()[1:4] for l in d.decode('utf-8','ignore').splitlines() if l.strip().startswith('vertex')]
        pts=[tuple(float(x) for x in v) for v in vs]
    else:
        n=struct.unpack('<I',d[80:84])[0]; pts=[]
        for i in range(n):
            v=struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12]
            pts += [v[0:3], v[3:6], v[6:9]]
    for p in pts:
        for j in range(3):
            lo[j]=min(lo[j],p[j]); hi[j]=max(hi[j],p[j])
print(' '.join('%.6f'%v for v in lo+hi))
PY
)"

L=$(awk -v a="$X0" -v b="$X1" 'BEGIN{printf "%.6f", b-a}')
if [ -z "$L" ] || [ "$(awk -v l="$L" 'BEGIN{print (l<=0)?1:0}')" = "1" ]; then echo "包围盒异常"; exit 1; fi

# 域: 上游 3L / 下游 6L / 侧向 3L
XU=$(awk -v x="$X1" -v l="$L" 'BEGIN{printf "%.4f", x+3*l}')
XL=$(awk -v x="$X0" -v l="$L" 'BEGIN{printf "%.4f", x-6*l}')
DY=$(awk -v a="$Y0" -v b="$Y1" -v l="$L" 'BEGIN{printf "%.4f", (b-a)/2+3*l}')
DZ=$(awk -v a="$Z0" -v b="$Z1" -v l="$L" 'BEGIN{printf "%.4f", (b-a)/2+3*l}')
CYM=$(awk -v a="$Y0" -v b="$Y1" 'BEGIN{printf "%.4f", (a+b)/2}')
CZM=$(awk -v a="$Z0" -v b="$Z1" 'BEGIN{printf "%.4f", (a+b)/2}')
Y0D=$(awk -v c="$CYM" -v d="$DY" 'BEGIN{printf "%.4f", c-d}')
Y1D=$(awk -v c="$CYM" -v d="$DY" 'BEGIN{printf "%.4f", c+d}')
Z0D=$(awk -v c="$CZM" -v d="$DZ" 'BEGIN{printf "%.4f", c-d}')
Z1D=$(awk -v c="$CZM" -v d="$DZ" 'BEGIN{printf "%.4f", c+d}')
# 基础网格: 弦长方向每 4 格一个弹长
NX=$(awk -v l="$L" -v xl="$XL" -v xu="$XU" 'BEGIN{printf "%d", int((xu-xl)/(l/4)+0.5)}')
NY=$(awk -v y0="$Y0D" -v y1="$Y1D" -v l="$L" 'BEGIN{printf "%d", int((y1-y0)/(l/4)+0.5)}')
NZ=$(awk -v z0="$Z0D" -v z1="$Z1D" -v l="$L" 'BEGIN{printf "%d", int((z1-z0)/(l/4)+0.5)}')

# 近体细化盒: 包围盒外扩 0.6L (避开壁面), 用它在 snappy 里做 level=BOX_LEVEL
BX0=$(awk -v x="$X0" -v l="$L" 'BEGIN{printf "%.4f", x-0.6*l}')
BX1=$(awk -v x="$X1" -v l="$L" 'BEGIN{printf "%.4f", x+0.6*l}')
BY0=$(awk -v c="$CYM" -v l="$L" -v d="$DY" 'BEGIN{printf "%.4f", c-(d<0.9*l?d:0.9*l)}')
BY1=$(awk -v c="$CYM" -v l="$L" -v d="$DY" 'BEGIN{printf "%.4f", c+(d<0.9*l?d:0.9*l)}')
BZ0=$(awk -v c="$CZM" -v l="$L" -v d="$DZ" 'BEGIN{printf "%.4f", c-(d<0.9*l?d:0.9*l)}')
BZ1=$(awk -v c="$CZM" -v l="$L" -v d="$DZ" 'BEGIN{printf "%.4f", c+(d<0.9*l?d:0.9*l)}')
# 流体内点: 上游偏一侧, 远离一切实体
Px=$(awk -v x="$X1" -v l="$L" 'BEGIN{printf "%.4f", x+1.5*l}')
Py=$(awk -v c="$CYM" -v l="$L" 'BEGIN{printf "%.4f", c+1.2*l}')
Pz=$(awk -v c="$CZM" -v l="$L" 'BEGIN{printf "%.4f", c+1.2*l}')

# 来流矢量: 空气相对弹体 = -V_B, V_B = V(cos a cos b, sin b, sin a cos b)
read -r UX UY UZ <<<"$(awk -v V="$V" -v a="$ALPHA" -v b="$BETA" 'BEGIN{
  pi=atan2(0,-1); A=a*pi/180; B=b*pi/180;
  printf "%.6f %.6f %.6f", -V*cos(A)*cos(B), -V*sin(B), -V*sin(A)*cos(B) }')"
KVAL=$(awk -v V="$V" -v I="$I_TURB" 'BEGIN{printf "%.6g", 1.5*(I*V)^2}')
OMVAL=$(awk -v k="$KVAL" -v l="$L" 'BEGIN{printf "%.6g", sqrt(k)/(0.09^0.25*0.07*l)}')
COFR=0    # 几何已按质心为原点导出
# 参考面积/长度: 按几何包围盒取迎流截面积 pi/4 * (横截面特征尺寸)^2
SREF=$(awk -v y0="$Y0" -v y1="$Y1" -v z0="$Z0" -v z1="$Z1" 'BEGIN{
  dy=y1-y0; dz=z1-z0; d=(dy>dz)?dy:dz; printf "%.9f", 3.141592653589793/4*d*d}')
LREF=$(awk -v y0="$Y0" -v y1="$Y1" -v z0="$Z0" -v z1="$Z1" 'BEGIN{
  dy=y1-y0; dz=z1-z0; d=(dy>dz)?dy:dz; printf "%.4f", d}')

mkdir -p "$DEST"
cp -r "$HERE/case_template/." "$DEST/"
mkdir -p "$DEST/constant/triSurface"
cp "$GEOM"/*.stl "$DEST/constant/triSurface/"

# ---- 按实际 STL 生成参数字典块 ----
GEN=""; REF=""; UBC=""; PBC=""; KBC=""; OBC=""; NBC=""; LIST=""
for f in $STLS; do
  s=${f%.stl}
  GEN+="    $s { type triSurfaceMesh; file \"$f\"; }"$'\n'
  # 薄舵单独级: fin_* 用 FIN_LEVEL, 其余 (body_*) 用 SURF_LEVEL
  case "$s" in
    fin_*) LVL=$FIN_LEVEL ;;
    *)     LVL=$SURF_LEVEL ;;
  esac
  REF+="        $s { level ($LVL $LVL); }"$'\n'
  UBC+="    $s { type noSlip; }"$'\n'
  PBC+="    $s { type zeroGradient; }"$'\n'
  KBC+="    $s { type kqRWallFunction; value uniform ${KVAL}; }"$'\n'
  OBC+="    $s { type omegaWallFunction; value uniform ${OMVAL}; }"$'\n'
  NBC+="    $s { type nutkWallFunction; value uniform 0; }"$'\n'
  LIST+="$s "
done

sub() { sed -i "s|$1|$2|g" "$3"; }

python3 - "$DEST" "$GEN" "$REF" "$UBC" "$PBC" "$KBC" "$OBC" "$NBC" "$LIST" <<'PY'
import sys, re, os
dest, gen, ref, ubc, pbc, kbc, obc, nbc, lst = sys.argv[1:10]
def rep(path, mapping):
    p = os.path.join(dest, path)
    s = open(p, encoding='utf-8').read()
    for k, v in mapping.items():
        s = s.replace(k, v)
    open(p, 'w', encoding='utf-8').write(s)
rep('system/snappyHexMeshDict', {'__SURFACES_GEOM__': gen, '__SURFACES_REFINE__': ref})
rep('0/U',     {'__SURFACES_U__': ubc})
rep('0/p',     {'__SURFACES_P__': pbc})
rep('0/k',     {'__SURFACES_K__': kbc})
rep('0/omega', {'__SURFACES_O__': obc})
rep('0/nut',   {'__SURFACES_N__': nbc})
rep('system/controlDict', {'__SURFACES_LIST__': lst.strip()})
PY

sub "__UINF__" "$UX $UY $UZ" "$DEST/0/U"
sub "__KVAL__" "$KVAL" "$DEST/0/k";        sub "__KIN__" "$KVAL" "$DEST/0/k"
sub "__OMEGAVAL__" "$OMVAL" "$DEST/0/omega"; sub "__OMEGAIN__" "$OMVAL" "$DEST/0/omega"
sub "__COFRX__" "$COFR" "$DEST/system/controlDict"
sub "__BOXMIN__" "$BX0 $BY0 $BZ0" "$DEST/system/snappyHexMeshDict"
sub "__BOXMAX__" "$BX1 $BY1 $BZ1" "$DEST/system/snappyHexMeshDict"
sub "__LOCINMESH__" "$Px $Py $Pz" "$DEST/system/snappyHexMeshDict"
sub "__BOXLEVEL__" "$BOX_LEVEL" "$DEST/system/snappyHexMeshDict"

# 边界层自动档 (10-30 拟真度对齐): T1(SURF_LEVEL>=6) 开 3 层, T0 不加 — 不破坏 T0 一致性
LAYERS=${LAYERS:-0}
if [ "${SURF_LEVEL:-5}" -ge 6 ]; then LAYERS=3; fi
LAYERS_BLOCK=' ".*" { nSurfaceLayers 3; } '
if [ "$LAYERS" -gt 0 ]; then
  sub "__ADDLAYERS__" "true" "$DEST/system/snappyHexMeshDict"
  sub "__LAYERS__" "$LAYERS_BLOCK" "$DEST/system/snappyHexMeshDict"
else
  sub "__ADDLAYERS__" "false" "$DEST/system/snappyHexMeshDict"
  sub "__LAYERS__" "" "$DEST/system/snappyHexMeshDict"
fi
sub "__XL__" "$XL" "$DEST/system/blockMeshDict"; sub "__XU__" "$XU" "$DEST/system/blockMeshDict"
sub "__Y0__" "$Y0D" "$DEST/system/blockMeshDict"; sub "__Y1__" "$Y1D" "$DEST/system/blockMeshDict"
sub "__Z0__" "$Z0D" "$DEST/system/blockMeshDict"; sub "__Z1__" "$Z1D" "$DEST/system/blockMeshDict"
sub "__NX__" "$NX" "$DEST/system/blockMeshDict"; sub "__NY__" "$NY" "$DEST/system/blockMeshDict"
sub "__NZ__" "$NZ" "$DEST/system/blockMeshDict"

cat > "$DEST/CASEINFO" <<EOF
V=$V
alpha=$ALPHA
beta=$BETA
U_inlet=($UX $UY $UZ)
k_inlet=$KVAL
omega_inlet=$OMVAL
rho=$RHO
S_ref=$SREF
L_ref=$LREF
L_turb=$(awk -v l="$L" 'BEGIN{printf "%.4f", 0.07*l}')
CofR=$COFR
geom_dir=$GEOM
surfaces=$LIST
EOF

echo "case -> $DEST"
echo "  geom L=${L}m  surfaces: $LIST"
echo "  U_inlet=($UX, $UY, $UZ)  k=$KVAL omega=$OMVAL"
echo "  block ${NX}x${NY}x${NZ}, 域 x[$XL,$XU] y[$Y0D,$Y1D] z[$Z0D,$Z1D]"
