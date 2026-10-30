#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生产端↔消费端风轴往返对拍 (10-31 底层审查沉淀的防线)

背景: lookup_aero.aero_forces 曾用 ŷ_B 投影造侧向基, 与生产端 post_process 的
标准稳定轴 (side=lift×drag) 在 αβ 同非零时差 ~3° 平面旋转, 角点 CY/CL 差 5-7%
——β=0 时两基重合, 任何只测 β=0 的自检都抓不到。本测试把生产端的基与合成
逐位复刻, 验证 coeffs→F_B 往返还原恒等, 角点+全域采样锁死, 防两端口径再漂移。

生产端约定 (openfoam/airframe-sweep/post_process.py wind_axes, 已用 CASEINFO
U_inlet 独立复算验证):
  v∞_B = V·(−cosαcosβ, −sinβ, −sinαcosβ)      # CASEINFO U_inlet 与此逐位一致
  lift = (ẑ_B 取反) 在垂直 v∞ 平面内投影归一   # 标准稳定轴
  side = lift × v∞̂
用法: 直接运行, 全过打印 PASS 并退出 0。依赖 numpy。
"""
import math
import sys

import numpy as np

from lookup_aero import AeroTable


def production_wind_axes(alpha_deg, beta_deg):
    """逐位复刻 post_process.wind_axes 的基矢量 (勿改 — 改动需两边同步+本测试重跑)。"""
    a, b = math.radians(alpha_deg), math.radians(beta_deg)
    vhat = np.array([math.cos(a) * math.cos(b), math.sin(b), math.sin(a) * math.cos(b)])
    drag = -vhat
    up0 = np.array([0.0, 0.0, -1.0])
    c = float(np.dot(up0, drag))
    lift = up0 - c * drag
    lift /= np.linalg.norm(lift)
    side = np.cross(lift, drag)
    return drag, lift, side


def make_table(alpha_bins, beta_bins, v_bins=(15.0, 20.0, 25.0, 30.0)):
    """构造系数恒定的合成表 (每 (α,β) 格给不同系数以便插值路径也受检)。"""
    values = {"V": list(v_bins), "alpha": list(alpha_bins), "beta": list(beta_bins),
              "de": [0.0], "da": [0.0], "dr": [0.0]}
    rows = []
    rng = np.random.default_rng(20261031)
    for v in v_bins:
        for a in alpha_bins:
            for b in beta_bins:
                rows.append([v, a, b, 0, 0, 0,
                             rng.uniform(-1, 1), rng.uniform(0, 1), rng.uniform(-0.2, 0.2),
                             rng.uniform(-0.8, 0.8), rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)])
    meta = {"S_REF": 0.010306121, "L_REF": 0.1146, "RHO": 1.225}
    return AeroTable(values, np.array(rows, float)[:, 6:], meta)


def main():
    table = make_table(np.linspace(-15, 15, 13), np.linspace(-15, 15, 7))
    qS = 0.5 * 1.225 * 20.0 ** 2 * 0.010306121
    qSL = qS * 0.1146
    worst = 0.0
    # 角点 + β=0 + 随机内点 (含非格点, 插值路径一并受检)
    samples = [(a, b) for a in (-15, -10, -7.5, 0, 7.5, 10, 15)
               for b in (-15, -10, -7.5, 0, 5, 10, 15)]
    rng = np.random.default_rng(7)
    samples += [(float(rng.uniform(-15, 15)), float(rng.uniform(-15, 15))) for _ in range(40)]
    for a, b in samples:
        c = table.coeffs(20.0, a, b, 0, 0, 0)
        drag, lift, side = production_wind_axes(a, b)
        F_prod = qS * (c["CD"] * drag + c["CL"] * lift + c["CY"] * side)
        M_prod = qSL * np.array([c["Cl"], c["Cm"], c["Cn"]])
        # 消费端: V_B = 弹体速度 = −v∞ (定常扫气的逆场景, 同一 (α,β) 语义)
        V_B = 20.0 * (-drag)
        F_cons, M_cons = table.aero_forces(V_B)
        err = float(np.max(np.abs(F_cons - F_prod)) / qS)
        errm = float(np.max(np.abs(M_cons - M_prod)) / qSL)
        worst = max(worst, err, errm)
        if err > 1e-12 or errm > 1e-12:
            print("FAIL (%.3f, %.3f): dF=%.3e dM=%.3e (系数级)" % (a, b, err, errm))
            return 1
    # β=0 特例仍在 (回归哨兵: 修复前旧基在 β=0 也是对的, 别把对的改坏)
    print("PASS: %d 采样点 (含全部角点) 往返还原恒等, 最大系数误差 %.2e" % (len(samples), worst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
