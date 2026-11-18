# -*- coding: utf-8 -*-
"""T0 拟真性验收全套 — 2026-11-08, 370 行主表 (V15/20/21/22/23/24/25/30) + 44 重跑对照.
锚定框架: fidelity_acceptance_1101.md §判据 + dataset_delivery §3.1 置信度."""
import csv, math, sys

MAIN = r"D:\WindTunnelSuite\wt_jobs\tmp\t0_table_370_1108.csv"
STRANDED = r"D:\WindTunnelSuite\wt_jobs\tmp\aero_table_stranded_1108.csv"
D2R = math.pi / 180.0
COLS = ["V", "alpha", "beta", "de", "da", "dr", "CL", "CD", "Cm", "CY", "Cl", "Cn"]

def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("v,"):
                continue
            r = line.split(",")
            if len(r) >= 12:
                rows.append({k: float(v) for k, v in zip(COLS, r[:12])})
    return rows

main_rows = load(MAIN)
stranded = load(STRANDED)
print(f"main={len(main_rows)}  stranded={len(stranded)}")

def lsq(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); sxy = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    k = sxy/sxx; b = my-k*mx
    ss = sum((y-my)**2 for y in ys)
    r2 = 1 - sum((y-(k*x+b))**2 for x,y in zip(xs,ys))/ss if ss > 0 else 1.0
    return k, b, r2

# ---------- 1. 进度 ----------
V_TARGET = {20.0, 21.0, 22.0, 23.0, 24.0, 25.0}
in_target = [r for r in main_rows if r["V"] in V_TARGET]
print(f"\n== 1.进度: 总行 {len(main_rows)} | 目标网格(V20-25) {len(in_target)}/546 "
      f"({len(in_target)/546*100:.1f}%) | 遗留 V15/V30 {len(main_rows)-len(in_target)}")
for V in sorted(V_TARGET):
    n = sum(1 for r in in_target if r["V"] == V)
    print(f"   V{V:.0f}: {n}/91")

# ---------- 2. 跨 V 钝感 (每个 (α,β) 姿态内, 系数随 V 的散布) ----------
print("\n== 2.跨V钝感 (姿态内 std/|mean|, 全部系数):")
by_att = {}
for r in main_rows:
    by_att.setdefault((r["alpha"], r["beta"]), []).append(r)
multi = {k: v for k, v in by_att.items() if len(v) >= 4}
worst = {}
for name in ("CL", "CD", "Cm", "CY", "Cl", "Cn"):
    spreads = []
    for k, rs in multi.items():
        vals = [r[name] for r in rs]
        m = sum(vals)/len(vals)
        if abs(m) < 1e-6:
            continue
        sd = (sum((v-m)**2 for v in vals)/len(vals))**.5
        spreads.append((abs(sd/m), k))
    spreads.sort(reverse=True)
    worst[name] = spreads[0] if spreads else (0, None)
    med = sorted(s for s,_ in spreads)[len(spreads)//2] if spreads else 0
    print(f"   {name}: 中位 {med*100:.2f}%  最差 {worst[name][0]*100:.2f}% @{worst[name][1]}  (n={len(spreads)} 姿态)")

# ---------- 3. 镜像对称 (α=0, β±对) ----------
print("\n== 3.镜像对称 (α=0):")
a0 = [r for r in main_rows if r["alpha"] == 0.0]
bmap = {r["beta"]: r for r in a0}
for b in (5.0, 10.0, 15.0):
    if b in bmap and -b in bmap:
        p, m = bmap[b], bmap[-b]
        cy = abs(p["CY"] + m["CY"]) / max(abs(p["CY"]), 1e-9) * 100/2
        cn = abs(p["Cn"] + m["Cn"]) / max(abs(p["Cn"]), 1e-9) * 100/2
        cl = abs(p["CL"] - m["CL"]) / max(abs(p["CL"]), 1e-9) * 100 if abs(p["CL"]) > 1e-6 else 0
        print(f"   β±{b:.0f}: CY反对称残差 {cy:.1f}%  Cn反对称残差 {cn:.1f}%  CL偶对称差 {cl:.1f}%")
# 全姿态 β 反对称: CY(α,β) ≈ -CY(α,-β) (X 构型镜像)
pairs = 0; tot = 0.0
for (a, b), rs in by_att.items():
    if b <= 0 or (a, -b) not in by_att:
        continue
    cy1 = sum(r["CY"] for r in rs)/len(rs)
    rs2 = by_att[(a, -b)]
    cy2 = sum(r["CY"] for r in rs2)/len(rs2)
    if abs(cy1) < 0.02:   # A3 锚: |CY|<0.03 网格偏置带, 跳过
        continue
    tot += abs(cy1 + cy2) / abs(cy1)
    pairs += 1
if pairs:
    print(f"   全姿态 CY 反对称平均残差: {tot/pairs*100:.1f}%  (n={pairs} 对, 排除网格偏置带)")

# ---------- 4. 斜率回归 (与 11-06 对照) ----------
print("\n== 4.静稳定导数 (对照 11-06: Cm_a +0.360 / Cn_b -0.434 / CL_a +2.406 / CY_b -2.311):")
b0 = [r for r in main_rows if r["beta"] == 0.0 and abs(r["alpha"]) <= 10]
a0f = [r for r in main_rows if r["alpha"] == 0.0 and abs(r["beta"]) <= 10]
for name, pts, prev in (("CL_a", b0, "+2.406"), ("Cm_a", b0, "+0.360"),
                         ("CY_b", a0f, "-2.311"), ("Cn_b", a0f, "-0.434")):
    xs = [r["alpha"] if name.endswith("a") else r["beta"] for r in pts]
    ys = [r[name.replace("_a", "").replace("_b", "")] if False else
          r[{"CL_a":"CL","Cm_a":"Cm","CY_b":"CY","Cn_b":"Cn"}[name]] for r in pts]
    k, b, r2 = lsq(xs, ys)
    print(f"   {name}: {k/D2R:+.4f}/rad  (n={len(pts)} R2={r2:.4f})  [11-06 {prev}]")

# ---------- 5. 压心自洽 (β=0): x_cp/L_REF = -Cm/CL ----------
print("\n== 5.压心 (β=0, V=20/22/24 各 α):")
for V in (20.0, 22.0, 24.0):
    xcs = []
    for r in sorted([r for r in b0 if r["V"] == V], key=lambda r: r["alpha"]):
        if abs(r["CL"]) > 0.05:
            xcs.append((r["alpha"], -r["Cm"]/r["CL"]))
    if xcs:
        s = ", ".join(f"a{a:+.0f}:{x*114.6:+.1f}mm" for a, x in xcs)
        print(f"   V{V:.0f}: {s}")

# ---------- 6. 重跑重复性 (44 对照对) ----------
print("\n== 6.重跑重复性 (同工况独立二次求解):")
main_map = {}
for r in main_rows:
    main_map.setdefault((r["V"], r["alpha"], r["beta"]), r)
pairs = []
for s in stranded:
    k = (s["V"], s["alpha"], s["beta"])
    if k in main_map:
        pairs.append((k, main_map[k], s))
print(f"   可配对: {len(pairs)}/{len(stranded)}")
for name in ("CL", "CD", "Cm", "CY", "Cn"):
    ds = []
    for k, r1, r2 in pairs:
        d = abs(r1[name] - r2[name])
        scale = max(abs(r1[name]), abs(r2[name]), 0.02)
        ds.append(d/scale*100)
    if ds:
        ds.sort()
        print(f"   {name}: 中位 {ds[len(ds)//2]:.2f}%  最差 {ds[-1]:.2f}%  (n={len(ds)})")
