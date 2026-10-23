#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hinges.json (模型系 mm) + 体积质心 → 最终 airframe_assembly.json (B 系, m)

每组舵选「轴向长度最长」的圆柱轴为铰链轴 (贯穿舵展的销轴),
空心圆柱轴套与之同轴 — 即曼波指定的「空心圆柱部分轴心」。

输出: cad/v1/cfd/airframe_assembly.json
  control_surfaces[].hinge_line = B 系两端点 [m]; mix 留 null (混控归电控仿真侧)
  扫气协议 = 4 片舵独立角度 δ1..δ4 (deflect_stl.py --angles)
"""
import json
import math
import sys

SRC = "cad/v1/hinges.json"
DST = "cad/v1/cfd/airframe_assembly.json"
COM_MODEL_MM = [-0.1, 0.2, 105.5]     # step_to_airframe 输出的体积加权质心

hinges = json.load(open(SRC, encoding="utf-8"))
by_part = {}
for h in hinges:
    by_part.setdefault(h["part_tag"], []).append(h)

def to_b_point(p_mm):
    return [-(p_mm[2] - COM_MODEL_MM[2]) / 1000.0,
            (p_mm[1] - COM_MODEL_MM[1]) / 1000.0,
            (p_mm[0] - COM_MODEL_MM[0]) / 1000.0]

def to_b_vec(a):
    v = [-a[2], a[1], a[0]]
    ln = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / ln for x in v]

surfaces = []
for i, tag in enumerate(sorted(by_part), 1):
    cand = sorted(by_part[tag], key=lambda h: -h["length_mm"])
    h = cand[0]                                # 贯穿舵展的销轴
    c = h.get("center_mm") or [h["point_mm"][k] + h["axis"][k] * h["length_mm"] / 2 for k in range(3)]
    a = to_b_vec(h["axis"])
    half = h["length_mm"] / 2000.0 * 1.15      # 两端各延 15% 保证覆盖舵展
    pB = to_b_point(c)
    p1 = [pB[k] - a[k] * half for k in range(3)]
    p2 = [pB[k] + a[k] * half for k in range(3)]
    surfaces.append(dict(
        name=f"fin_{i}", mesh=f"fin_{i}.stl",
        hinge_line=[[round(v, 6) for v in p1], [round(v, 6) for v in p2]],
        hinge_axis=[round(v, 5) for v in a],
        hinge_len_mm=h["length_mm"], hinge_radius_mm=h["radius_mm"],
        range_deg=[-20.0, 20.0],
        mix=None,
        flip=False,
        status="已定 (空心圆柱销轴, 最长贯穿轴; 如与实物不符改这一行)",
        source_tag=tag,
        alternates=[dict(r=x["radius_mm"], L=x["length_mm"],
                         point=x["point_mm"], axis=x["axis"])
                    for x in cand[1:6]]))

asm = dict(
    version="v1.1 (STEP 铰链轴定稿)",
    frame="B: x 前弹轴, y 右, z 下, 右手系; 原点 = 体积加权质心",
    source_step="airframe.step",
    fin_thickness_note="舵面气动面最大厚度 4mm (曼波 2026-10-23 定); bbox 8mm 含圆角/凸台",
    sweep_protocol=dict(
        note="曼波职责 = 镖体位姿 × 舵面自由度 的气动; 混控归电控仿真侧",
        angles="4 片舵独立角 δ1..δ4 (deg), deflect_stl.py --angles '{\"fin_1\":5,...}'",
        state="V, alpha, beta + delta[4] → 6 系数 (长表 append)",
        table="guidance_sim/aero/aero_table.csv; RL 期间按需增量补点 (append-only + 热加载)"),
    body=dict(mesh="body.stl", mass_kg=0.0, com=[0.0, 0.0, 0.0], inertia_diag=[0.0, 0.0, 0.0],
              note="质量/惯量待 Fusion 物理属性或实机称重"),
    control_surfaces=surfaces,
    layout_note="4 片 45° X 布局尾缘舵; δi 独立, 电控侧自行实现 δ↔(de,da,dr) 混控",
    control_sign=dict(de_positive_means="由电控混控定义 (CFD 侧只认 δi 符号 = 绕 hinge_axis 右手正转)"))

json.dump(asm, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"-> {DST}")
for s in surfaces:
    print(f"  {s['name']} (tag{s['source_tag']}): r={s['hinge_radius_mm']}mm L={s['hinge_len_mm']}mm "
          f"axis={s['hinge_axis']}")
    print(f"     hinge_line: {s['hinge_line'][0]} -> {s['hinge_line'][1]}")
    print(f"     备选轴 {len(s['alternates'])} 条已存 alternates")
