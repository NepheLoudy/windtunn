#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP (AP203/AP214) 结构探针 v2 — 按装配树应用变换, 输出每个实例的世界坐标包围盒

用法:
  python3 step_probe.py <file.step> [--json out.json] [--min 5]   # --min 单位 mm
输出: 实例列表 (产品名/包围盒尺寸/中心)、整体包围盒、单位与缩放。

依赖: 仅标准库。
"""
import argparse
import json
import math
import re
import sys
from collections import deque


def parse_step(path):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    i = txt.find("DATA;")
    if i < 0:
        raise ValueError("不是 STEP 文件 (找不到 DATA;)")
    txt = txt[i + 5:]
    ents, cur, inq = {}, [], False
    for ch in txt:
        cur.append(ch)
        if ch == "'":
            inq = not inq
        elif ch == ";" and not inq:
            stmt = "".join(cur).strip()
            cur = []
            m = re.match(r"#(\d+)\s*=\s*(.*)", stmt, re.S)
            if m:
                ents[int(m.group(1))] = m.group(2).strip()
    return ents, txt


def refs_of(body):
    return [int(x) for x in re.findall(r"#(\d+)", body)]


def first_ref(body):
    r = refs_of(body)
    return r[0] if r else None


def unit_scale(ents):
    for body in ents.values():
        if "SI_UNIT" in body and "LENGTH_UNIT" in body:
            if ".MILLI." in body:
                return 1e-3, "mm"
            if ".CENTI." in body:
                return 1e-2, "cm"
            return 1.0, "m"
    for body in ents.values():
        if "CONVERSION_BASED_UNIT" in body and "LENGTH" in body:
            return 1e-3, "conversion(m?)"
    return 1.0, "unknown"


# ---------------- 3D 变换 ----------------

def axis_placement(ents, eid):
    """AXIS2_PLACEMENT_3D(#loc, #axis, #ref) → 4x4 (列: x y z, 平移 loc)。"""
    body = ents[eid]
    r = refs_of(body)
    loc = [0.0, 0.0, 0.0]
    if r:
        lb = ents.get(r[0], "")
        m = re.search(r"\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)", lb)
        if m:
            loc = [float(x) for x in m.groups()]
    z = [0.0, 0.0, 1.0]
    xref = [1.0, 0.0, 0.0]
    if len(r) > 1:
        m = re.search(r"\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)",
                      ents.get(r[1], ""))
        if m:
            z = [float(v) for v in m.groups()]
    if len(r) > 2:
        m = re.search(r"\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)",
                      ents.get(r[2], ""))
        if m:
            xref = [float(v) for v in m.groups()]

    def n(v):
        l = math.sqrt(sum(c * c for c in v)) or 1.0
        return [c / l for c in v]
    z = n(z)
    x = [xref[i] - sum(xref[j] * z[j] for j in range(3)) * z[i] for i in range(3)]
    x = n(x)
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return [[x[0], y[0], z[0], loc[0]],
            [x[1], y[1], z[1], loc[1]],
            [x[2], y[2], z[2], loc[2]],
            [0, 0, 0, 1]]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_inv_rigid(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [m[i][3] for i in range(3)]
    ti = [-sum(r[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [[r[0][0], r[0][1], r[0][2], ti[0]],
            [r[1][0], r[1][1], r[1][2], ti[1]],
            [r[2][0], r[2][1], r[2][2], ti[2]],
            [0, 0, 0, 1]]


def apply(m, p):
    return [sum(m[i][k] * p[k] for k in range(3)) + m[i][3] for i in range(3)]


def build_transforms(ents):
    """返回 (rep→parent_rep 的变换表, rep→product_name)。"""
    # rep -> product definition shape
    rep2pds, pds2rep = {}, {}
    for eid, body in ents.items():
        if body.startswith("SHAPE_DEFINITION_REPRESENTATION"):
            r = refs_of(body)
            if len(r) >= 2:
                pds2rep[r[0]] = r[1]
                rep2pds[r[1]] = r[0]
    # pds -> product definition
    pds2pd = {}
    for eid, body in ents.items():
        if body.startswith("PRODUCT_DEFINITION_SHAPE"):
            r = refs_of(body)
            if r:
                pds2pd[eid] = r[0]
    # pd -> product name
    pd2name = {}
    for eid, body in ents.items():
        if body.startswith("PRODUCT_DEFINITION("):
            r = refs_of(body)
            if r:
                pdf = r[0]
                pr = first_ref(ents.get(pdf, ""))
                if pr is not None and pr in ents and ents[pr].startswith("PRODUCT("):
                    m = re.search(r"PRODUCT\(\s*'([^']*)'", ents[pr])
                    pd2name[eid] = m.group(1) if m else f"#{eid}"
    # NAUO: child pd -> parent pd
    child2parent_pd = {}
    for eid, body in ents.items():
        if body.startswith(("NEXT_ASSEMBLY_USAGE_OCCURRENCE", "ASSEMBLY_COMPONENT_USAGE")):
            r = refs_of(body)
            if len(r) >= 2:
                child2parent_pd[r[1]] = r[0]

    # CDSR: rep1(子) → rep2(父) 的变换
    rep2parent = {}
    for eid, body in ents.items():
        if body.startswith("CONTEXT_DEPENDENT_SHAPE_REPRESENTATION"):
            r = refs_of(body)
            if len(r) < 2:
                continue
            rr, pds = r[0], r[1]
            rb = ents.get(rr, "")
            tr = refs_of(rb)
            if len(tr) < 2:
                continue
            rep1, rep2 = tr[0], tr[1]
            # 变换名/描述可能是 $，ITS 在最后
            ids = [x for x in tr if x in ents and ents[x].startswith("ITEM_DEFINED_TRANSFORMATION")]
            if not ids:
                continue
            tr_refs = refs_of(ents[ids[0]])
            tr_refs = [x for x in tr_refs if x in ents and "AXIS2_PLACEMENT_3D" in ents[x]]
            if len(tr_refs) < 2:
                continue
            a1 = axis_placement(ents, tr_refs[0])
            a2 = axis_placement(ents, tr_refs[1])
            t = mat_mul(a2, mat_inv_rigid(a1))
            rep2parent[rep1] = (rep2, t)

    rep2name = {}
    for rep, pds in rep2pds.items():
        pd = pds2pd.get(pds)
        if pd in pd2name:
            rep2name[rep] = pd2name[pd]
    return rep2parent, rep2name


def collect_points(ents, root, maxnodes=600000):
    seen, q, pts = set(), deque([root]), []
    pt_re = re.compile(r"([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)")
    while q:
        eid = q.popleft()
        if eid in seen or eid not in ents:
            continue
        seen.add(eid)
        body = ents[eid]
        if body.startswith("CARTESIAN_POINT"):
            m = pt_re.search(body)
            if m:
                pts.append(tuple(float(x) for x in m.groups()))
            continue
        q.extend(refs_of(body))
        if len(seen) > maxnodes:
            break
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--json", default=None)
    ap.add_argument("--min", type=float, default=5.0, help="mm, 小于该最大边的实体视为碎屑")
    args = ap.parse_args()

    ents, _ = parse_step(args.step)
    scale, unit = unit_scale(ents)
    rep2parent, rep2name = build_transforms(ents)
    print(f"实体数 {len(ents)} | 单位 {unit} (×{scale}) | 装配变换 {len(rep2parent)}")

    solids = [eid for eid, b in ents.items() if b.startswith(("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS"))]
    # 找每个 solid 所在的 rep (其祖先链上第一个有变换的 rep)
    rep_items = {}
    for eid, body in ents.items():
        if body.startswith("ADVANCED_BREP_SHAPE_REPRESENTATION") or body.startswith("SHAPE_REPRESENTATION("):
            rep_items[eid] = refs_of(body)

    # solid -> 直接父 rep: 用 BFS 反向不行, 改为: 每个 rep 的 items 里逐项展开找 solid
    solid_owner = {}
    for rep, items in rep_items.items():
        stack = list(items)
        seen = set()
        while stack:
            x = stack.pop()
            if x in seen or x not in ents:
                continue
            seen.add(x)
            if ents[x].startswith(("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS")):
                solid_owner.setdefault(x, rep)
            stack.extend(refs_of(ents[x]))

    rows = []
    for sid in solids:
        rep = solid_owner.get(sid)
        if rep is None:
            continue
        # 累积变换到根
        m, cur, gu = [[1 if i == j else 0 for j in range(4)] for i in range(4)], rep, 0
        while cur in rep2parent and gu < 50:
            parent, t = rep2parent[cur]
            m = mat_mul(t, m)
            cur = parent
            gu += 1
        pts = collect_points(ents, sid)
        if not pts:
            continue
        wp = [apply(m, p) for p in pts]
        lo = [min(p[i] for p in wp) for i in range(3)]
        hi = [max(p[i] for p in wp) for i in range(3)]
        rows.append(dict(id=sid, rep=rep, name=rep2name.get(rep, "?"), lo=lo, hi=hi,
                         dim=[hi[i] - lo[i] for i in range(3)],
                         ctr=[(hi[i] + lo[i]) / 2 for i in range(3)], gen=gu))

    rows.sort(key=lambda r: -max(r["dim"]))
    k = scale * 1000.0          # 文件值 → mm
    print(f"\n{'solid':>7} {'尺寸 (mm)':>28} {'中心 (mm)':>30} {'深度':>4}  产品")
    for r in rows:
        if max(r["dim"]) * k < args.min:
            continue
        print(f"  #{r['id']:<5} "
              f"{r['dim'][0]*k:7.1f}×{r['dim'][1]*k:7.1f}×{r['dim'][2]*k:7.1f}  "
              f"({r['ctr'][0]*k:7.1f},{r['ctr'][1]*k:7.1f},{r['ctr'][2]*k:7.1f})  "
              f"{r['gen']:3d}  {r['name'][:15]}")

    if rows:
        lo = [min(r["lo"][i] for r in rows) for i in range(3)]
        hi = [max(r["hi"][i] for r in rows) for i in range(3)]
        print("\n整体包围盒 (mm): "
              f"({lo[0]*k:.1f},{lo[1]*k:.1f},{lo[2]*k:.1f}) → "
              f"({hi[0]*k:.1f},{hi[1]*k:.1f},{hi[2]*k:.1f})")
        print("整体尺寸 (mm): "
              f"{(hi[0]-lo[0])*k:.1f} × {(hi[1]-lo[1])*k:.1f} × {(hi[2]-lo[2])*k:.1f}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
        print(f"json -> {args.json}")


if __name__ == "__main__":
    main()
