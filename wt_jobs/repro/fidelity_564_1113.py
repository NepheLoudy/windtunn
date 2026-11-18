# -*- coding: utf-8 -*-
"""T0 564 行拟真性全套 — 2026-11-13, 对标 dataset_delivery.md 规划特征逐条验收.
对照 11-08 电池 + 11-06 翻案值 + 交付文档 §3 特征表."""
import csv, math, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\WindTunnelSuite\wt_jobs\tmp\t0_table_564_1113.csv"
COLS = ["V","alpha","beta","de","da","dr","CL","CD","Cm","CY","Cl","Cn"]
D2R = math.pi/180.0

rows = []
with open(path, newline="", encoding="utf-8-sig") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("v,"):
            continue
        r = line.split(",")
        if len(r) >= 12:
            rows.append({k: float(v) for k, v in zip(COLS, r[:12])})
print(f"rows={len(rows)}")

def lsq(xs, ys):
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
    sxx=sum((x-mx)**2 for x in xs); sxy=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    k=sxy/sxx; b=my-k*mx
    ss=sum((y-my)**2 for y in ys)
    r2=1-sum((y-(k*x+b))**2 for x,y in zip(xs,ys))/ss if ss>0 else 1.0
    return k,b,r2

# --- 进度 ---
in_t=[r for r in rows if r["V"] in (20.,21.,22.,23.,24.,25.)]
print(f"\n[进度] in-target {len(in_t)}/546, 遗留V15/30 {len(rows)-len(in_t)}")

# --- 静稳导数 (含正α盲区补齐检查) ---
b0=[r for r in rows if r["beta"]==0.0]
a0=[r for r in rows if r["alpha"]==0.0]
neg=[r for r in b0 if -10<=r["alpha"]<=0]
pos=[r for r in b0 if 0<=r["alpha"]<=10]
allb=[r for r in b0 if abs(r["alpha"])<=10]
for name,ch,pts,prev in (("CL_a","CL",allb,"+2.41"),("Cm_a(全±10)","Cm",allb,"+0.35"),
                          ("Cm_a(负半)","Cm",neg,"+0.60/-0.21分段"),("Cm_a(正半)","Cm",pos,"(新盲区)")):
    if len(pts)>=3:
        k,b,r2=lsq([p["alpha"] for p in pts],[p[ch] for p in pts])
        print(f"[斜率] {name}: {k/D2R:+.4f}/rad (n={len(pts)} R2={r2:.3f}) [11-08 {prev}]")
bb=[r for r in a0 if abs(r["beta"])<=10]
for name,ch,prev in (("CY_b","CY","-2.311"),("Cn_b","Cn","-0.434")):
    if len(bb)>=3:
        k,b,r2=lsq([p["beta"] for p in bb],[p[ch] for p in bb])
        print(f"[斜率] {name}: {k/D2R:+.4f}/rad (n={len(bb)} R2={r2:.3f}) [11-08 {prev}]")

# --- 镜像对称 (全姿态 CY 反对称) ---
by_att={}
for r in rows:
    by_att.setdefault((r["alpha"],r["beta"]),[]).append(r)
tot=0.0; pairs=0; worst=(0,None)
for (a,b),rs in by_att.items():
    if b<=0 or (a,-b) not in by_att: continue
    cy1=sum(r["CY"] for r in rs)/len(rs)
    cy2=sum(r["CY"] for r in by_att[(a,-b)])/len(by_att[(a,-b)])
    if abs(cy1)<0.02: continue
    res=abs(cy1+cy2)/abs(cy1)
    tot+=res; pairs+=1
    if res>worst[0]: worst=(res,(a,b))
if pairs:
    print(f"[镜像] CY 反对称平均 {tot/pairs*100:.1f}% (n={pairs}), 最差 {worst[0]*100:.1f}% @{worst[1]}")

# --- 跨V钝感 ---
multi={k:v for k,v in by_att.items() if len(v)>=4}
for name in ("CL","CD"):
    sp=[]
    for k,rs in multi.items():
        vals=[r[name] for r in rs]; m=sum(vals)/len(vals)
        if abs(m)<1e-6: continue
        sd=(sum((v-m)**2 for v in vals)/len(vals))**.5
        sp.append(sd/abs(m))
    sp.sort()
    print(f"[跨V] {name} 中位 {sp[len(sp)//2]*100:.2f}% 最差 {sp[-1]*100:.1f}% (n={len(sp)})")

# --- 压心自洽 (β=0, V=22) ---
xcs=[]
for r in sorted([r for r in b0 if r["V"]==22.],key=lambda r:r["alpha"]):
    if abs(r["CL"])>0.05:
        xcs.append((r["alpha"], -r["Cm"]/r["CL"]))
if xcs:
    print("[压心] V22 β=0:", ", ".join(f"a{a:+.0f}:{x*114.6:+.1f}mm" for a,x in xcs))

# --- β 深水区 (±15 失速回落) ---
print("[β深水] α=0 Cn(β) 序列:", {int(r["beta"]): round(r["Cn"],4) for r in sorted(a0,key=lambda r:r["beta"])})

# --- CL_α 线性度 (弯折点检测, ±15 全剖面) ---
full=[r for r in b0 if r["V"]==22.]
if full:
    print("[CL全剖] V22 β=0:", ", ".join(f"a{r['alpha']:+.0f}:{r['CL']:+.3f}" for r in sorted(full,key=lambda r:r["alpha"])))
