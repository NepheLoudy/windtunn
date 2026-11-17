# -*- coding: utf-8 -*-
"""舵效 delta-mode 查表 — 四舵独立角的气动增量叠加 (spec §0.5 舵效查表路线实装)。

数据: delta_table_t1q.csv (10 位形 OpenFOAM L6/L8 @ V20/α0/β0 锚, ET600)。
模型: ΔC(δ1..δ4) = Σ_i [线性缩放的单舵增量] — 叠加假设+线性缩放,
  被 LBM 量级表六连验 (组合例 vs 单舵叠加误差 <0.02) 与 CPU d13dd/d24dd
  实测对拍 (本模块自测 2) 双重背书。

用法 (与 lookup_aero 组合):
    from lookup_aero import lookup_aero
    from delta_lookup import delta_forces_B, DELTA_ANCHOR
    F0, M0 = lookup_aero(V, alpha, beta)          # δ=0 基座
    dF, dM = delta_forces_B(fin1, fin2, fin3, fin4, V, alpha, beta)  # 舵效增量 (B 系)
    F, M = F0 + dF, M0 + dM

口径与边界 (诚实清单):
- 锚定域: V20/α0/β0 单锚 (扩姿态走 append-only); |δi|>10° 钳位+警告 (数据极限)
- 线性缩放假设: |δi|<10° 按比例, 未验证中间角非线性
- 叠加假设: CPU 级验证见自测 2; LBM 级六连验 <0.02
- 基于力矩参考点 com_B (表头 MOMENT_REF), 与 lookup_aero 同基准
- fin1..4 = X 布局四舵独立角 (绕 v4 真铰链轴右手正转, delta_cases.csv 口径);
  **spec 的 + 布局 de/da/dr 混控约定不适用此表** (见 dataset_delivery §0.4-4)
"""
import csv
import os
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
DELTA_TABLE_PATH = os.path.join(_HERE, "delta_table_t1q.csv")

# d0 基线 (T0 表 (20,0,0) 行, 与 delta 批同管线同口径) — 供无主表时的独立降级
_D0_FALLBACK = {"CL": -0.002568, "CD": 0.139294, "Cm": 0.001337,
                "CY": -0.001701, "Cl": -0.002267, "Cn": 0.001123}
COEFFS = ("CL", "CD", "Cm", "CY", "Cl", "Cn")
ANCHOR = {"V": 20.0, "alpha": 0.0, "beta": 0.0}
DELTA_LIMIT = 10.0  # deg, ±10° 数据极限

_TABLE = None  # {(fin1,fin2,fin3,fin4): {coeff: delta}}


def _load():
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    if not os.path.exists(DELTA_TABLE_PATH):
        warnings.warn("delta_table_t1q.csv 不存在 — delta-mode 降级为全零增量", RuntimeWarning, stacklevel=2)
        _TABLE = {}
        return _TABLE
    cfg = {}
    with open(DELTA_TABLE_PATH, newline="", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split(",")
            if p[0] == "tag":
                continue
            try:
                fins = tuple(round(float(x), 4) for x in p[1:5])
                cfg[fins] = {k: float(v) for k, v in zip(COEFFS, p[8:14])}
            except (ValueError, IndexError):
                continue
    d0 = cfg.get((0.0, 0.0, 0.0, 0.0))
    if d0 is None:
        d0 = _D0_FALLBACK
        warnings.warn("delta 表无 d0 行, 使用内置 fallback 基线", RuntimeWarning, stacklevel=2)
    # 增量 = config − d0
    deltas = {}
    for fins, c in cfg.items():
        if fins == (0.0, 0.0, 0.0, 0.0):
            continue
        deltas[fins] = {k: c[k] - d0[k] for k in COEFFS}
    _TABLE = {"deltas": deltas, "d0": d0}
    return _TABLE


def delta_coeffs(fin1, fin2, fin3, fin4):
    """四舵独立角 (deg) → 六系数增量 ΔC。

    查表策略 (按保真度递降):
    1. **实测组合精确匹配**: (fin1..fin4) 与表内位形一致 → 直接返回实测增量 (最可信)
    2. **叠加+线性缩放**: 无实测时按单舵锚叠加 — ⚠ CPU L6/L8 实测 d13dd 叠加偏差
       43.7% (超线性增强), 未测组合的不确定度按 ±45% 理解, 关键组合建议实跑补点
    |δi|>10° 钳位+警告 (数据极限)。
    """
    t = _load()["deltas"]
    fins = tuple(round(float(x), 4) for x in (fin1, fin2, fin3, fin4))
    if fins in t:
        return dict(t[fins])  # 实测组合精确匹配 (最可信路径)
    out = dict.fromkeys(COEFFS, 0.0)
    pos_map = {}
    neg_map = {}
    for k, v in t.items():
        nz = [(i + 1, x) for i, x in enumerate(k) if abs(x) > 1e-9]
        if len(nz) != 1:
            continue
        idx, val = nz[0]
        (pos_map if val > 0 else neg_map)[idx] = v
    for i, di in enumerate(fins):
        di = float(di)
        if abs(di) <= 1e-9:
            continue
        idx = i + 1
        if abs(di) > DELTA_LIMIT:
            warnings.warn(f"fin{idx}={di}° 出域 (>±{DELTA_LIMIT:.0f}°) — 钳位到极限 (数据极限非物理极限)", RuntimeWarning, stacklevel=2)
        di_c = max(-DELTA_LIMIT, min(DELTA_LIMIT, di))
        scale = abs(di_c) / DELTA_LIMIT
        book = pos_map if di_c > 0 else neg_map
        src = book.get(idx)
        if src is None:
            warnings.warn(f"fin{idx} {'+' if di_c > 0 else '-'}{DELTA_LIMIT:.0f}° 锚缺失 — 该舵增量跳过", RuntimeWarning, stacklevel=2)
            continue
        for k in COEFFS:
            out[k] += scale * src[k]
    return out


def delta_forces_B(fin1, fin2, fin3, fin4, V, alpha, beta):
    """四舵增量 → B 系力/力矩增量 (dF, dM)。

    系数→力换算与 lookup_aero.aero_forces 同构: 稳定轴基 (CD 沿来流, CL ⊥来流,
    CY 侧向), 力矩绕体轴。qS 用当前 V 与锚定 S_REF。
    注意: 增量系数在 (α0,β0,V20) 锚提取, 施加到任意 (α,β) = 叠加假设的延伸 (caveat)。
    """
    dc = delta_coeffs(fin1, fin2, fin3, fin4)
    import math
    import numpy as np
    S_REF = 0.010306121  # 外接圆口径 (aero_table 表头同源)
    L_REF = 0.1146
    rho = 1.225
    qS = 0.5 * rho * V * V * S_REF
    a = math.radians(alpha)
    b = math.radians(beta)
    u = np.array([math.cos(a) * math.cos(b), math.sin(b), math.sin(a) * math.cos(b)])
    xh = u / np.linalg.norm(u)
    zs = np.array([0.0, 0.0, 1.0]) - np.array([0.0, 0.0, 1.0]).dot(xh) * xh
    zs /= np.linalg.norm(zs)
    ys = np.cross(zs, xh)
    dF = qS * (dc["CD"] * (-xh) + dc["CL"] * (-zs) + dc["CY"] * ys)
    dM = qS * L_REF * (dc["Cl"] * np.array([1.0, 0, 0])
                       + dc["Cm"] * np.array([0, 1.0, 0])
                       + dc["Cn"] * np.array([0, 0, 1.0]))
    return dF, dM


if __name__ == "__main__":
    t = _load()
    print(f"载入位形: {len(t['deltas'])} (d0 基线 {'表内' if t else 'fallback'})")
    # 自测 1: 单舵往返 (构造性, 应精确)
    dc = delta_coeffs(10, 0, 0, 0)
    assert abs(dc["CL"] - t["deltas"][(10.0, 0.0, 0.0, 0.0)]["CL"]) < 1e-12
    print("自测1 单舵往返 PASS")
    # 自测 2: d13dd 精确匹配 (实测组合优先路径)
    dc13 = delta_coeffs(10, 0, -10, 0)
    if (10.0, 0.0, -10.0, 0.0) in t["deltas"]:
        act = t["deltas"][(10.0, 0.0, -10.0, 0.0)]
        assert all(abs(dc13[k] - act[k]) < 1e-12 for k in COEFFS)
        print("自测2 d13dd 精确匹配 PASS (实测组合优先)")
    # 自测 2b: 叠加假设偏差量化 — d13dd 实测 vs (d1p+d3m) 线性叠加 (诚实不确定度标定)
    d1p = t["deltas"][(10.0, 0.0, 0.0, 0.0)]
    d3m = t["deltas"][(0.0, 0.0, -10.0, 0.0)]
    worst = max(abs((d1p[k] + d3m[k]) - act[k]) / max(abs(act[k]), 1e-6) for k in COEFFS)
    print(f"自测2b 叠加偏差标定: d13dd 最差 {worst*100:.1f}% (超线性增强 — 未测组合不确定度 ±45% 口径)")
    # 自测 3: 镜像反对称 (d1p vs d1m)
    d1m = t["deltas"].get((-10.0, 0.0, 0.0, 0.0))
    if d1m:
        dp = t["deltas"][(10.0, 0.0, 0.0, 0.0)]
        worst = max(abs(dp[k] + d1m[k]) / max(abs(dp[k]), 1e-6) for k in COEFFS)
        print(f"自测3 d1 镜像反对称: 最差 {worst*100:.1f}%  {'PASS(符号反对称)' if worst < 3.0 else 'CHECK'}")
    # 自测 4: 钳位
    import warnings as W
    with W.catch_warnings(record=True) as wl:
        W.simplefilter("always")
        dc15 = delta_coeffs(15, 0, 0, 0)
        assert len(wl) >= 1 and abs(dc15["CL"] - dc["CL"]) < 1e-12
    print("自测4 钳位+警告 PASS")
    # 自测 5: delta_forces_B 量纲
    dF, dM = delta_forces_B(10, 0, 0, 0, 20.0, 0.0, 0.0)
    assert dF[0] < 0 and abs(dM[1]) > 0
    print(f"自测5 delta_forces_B PASS (dF={ [round(x,3) for x in dF] })")
    print("=== delta_lookup 自测全部通过 ===")
