#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit A6: 几何基准外部锚检查 — 表内部自洽 (A1-A5) 之外的第六检

基准错误在表内部无迹可寻 (10-29 事故教训), 必须用几何层推出来的外部真值对照:
  锚1  δ=0 平行基准 → CY 全表 |median| 应 ≈0 (< 0.03), 且无恒定偏置
       (红基准折叠位实测 CY≈-0.13, 是折叠舵组净侧力; 蓝基准顺流位应归零)
  锚2  β 镜像对称恢复为判据: CL(α,β)=CL(α,-β), CY(α,β)=-CY(α,-β) (平行基准下成立)
       (红基准手性几何下不成立, 当时降级为指纹; 蓝基准 δ=0 对称构型恢复 PASS/FAIL)
  锚3  CL_α 斜率弹体主导, 两基准同工况对拍漂移应 < 8% (几何差异只在舵面)

用法: python audit_basis_check.py <aero_table.csv> [--compare <red_table.csv>]
输出: 每锚 PASS/FAIL/WARN + 证据数值; 退出码 0=全过 1=有 FAIL
纯标准库。
"""
import sys, csv, math, argparse

def load(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        lines = [ln for ln in f if not ln.startswith('#')]
    for r in csv.DictReader(lines):
        try:
            rows.append(dict(
                V=float(r['V']), alpha=float(r['alpha']), beta=float(r['beta']),
                CL=float(r['CL']), CD=float(r['CD']), Cm=float(r['Cm']),
                CY=float(r['CY']), Cl=float(r['Cl']), Cn=float(r['Cn'])))
        except (KeyError, ValueError):
            continue
    return rows

def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n//2] if n % 2 else 0.5*(xs[n//2-1]+xs[n//2])

def slope_cl_alpha(rows, beta=0.0):
    by_a = {}
    for r in rows:
        if abs(r['beta'] - beta) < 1e-6:
            by_a.setdefault(r['alpha'], []).append(r['CL'])
    xs = sorted(by_a)
    if len(xs) < 3:
        return None, len(xs)
    n = len(xs); mx = sum(xs)/n
    mys = [median(by_a[a]) for a in xs]; my = sum(mys)/n
    num = sum((x-mx)*(y-my) for x, y in zip(xs, mys))
    den = sum((x-mx)**2 for x in xs)
    return (num/den if den else None), n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('table')
    ap.add_argument('--compare', help='红基准表, 做 CL_α 漂移对拍')
    args = ap.parse_args()
    rows = load(args.table)
    if not rows:
        print('A6: 表空或格式不对'); sys.exit(1)
    fails = 0

    # 锚1: CY 恒定偏置 — 只看 β=0 行 (β≠0 的侧力是合法物理, 不能进这指标)
    cy0 = [abs(r['CY']) for r in rows if abs(r['beta']) < 1e-6]
    if not cy0:
        print('锚1 CY偏置 无 β=0 行  [SKIP]')
    else:
        med = median(cy0)
        ok = med < 0.03
        print('锚1 CY偏置 |median CY(β=0)| = %.4f over %d 行  (< 0.03)  [%s]'
              % (med, len(cy0), 'PASS' if ok else 'FAIL'))
        if not ok: fails += 1

    # 锚2: β 镜像 (只对 β≠0 且有配对的工况)
    bmap = {}
    for r in rows:
        bmap.setdefault((r['V'], r['alpha']), {})[round(r['beta'], 4)] = r
    n_pair = n_ok = 0
    errs_cl, errs_cy = [], []
    for (V, a), d in bmap.items():
        for b, r in d.items():
            if b <= 0 or -b not in d: continue
            m = d[-b]
            n_pair += 1
            e1 = abs(r['CL'] - m['CL']) / (abs(r['CL']) + abs(m['CL']) + 1e-9)
            e2 = abs(r['CY'] + m['CY']) / (abs(r['CY']) + abs(m['CY']) + 1e-9)
            errs_cl.append(e1); errs_cy.append(e2)
            if e1 < 0.10: n_ok += 1
    if n_pair:
        mc, my = median(errs_cl), median(errs_cy)
        ok = n_ok / n_pair >= 0.9 and mc < 0.05 and my < 0.10
        print('锚2 β镜像 CL对称率 %d/%d (中位偏差 %.3f) | CY反对称中位偏差 %.3f  [%s]'
              % (n_ok, n_pair, mc, my, 'PASS' if ok else ('WARN' if n_ok/n_pair >= 0.75 else 'FAIL')))
        if n_ok / n_pair < 0.75: fails += 1
    else:
        print('锚2 β镜像 无配对工况 (β 只扫了 0?)  [SKIP]')

    # 锚3: CL_α 漂移对拍
    s_blue, n_b = slope_cl_alpha(rows)
    print('锚3 CL_α(β=0) 蓝表斜率 = %s (n=%d α点)' % ('%.4f' % s_blue if s_blue else 'n/a', n_b))
    if args.compare:
        red = load(args.compare)
        s_red, n_r = slope_cl_alpha(red)
        if s_blue and s_red:
            drift = abs(s_blue - s_red) / abs(s_red)
            ok = drift < 0.08
            print('    红表斜率 = %.4f (n=%d) → 漂移 %.2f%% (< 8%%)  [%s]'
                  % (s_red, n_r, drift*100, 'PASS' if ok else 'FAIL'))
            if not ok: fails += 1
        else:
            print('    红表 β=0 行 α 点不足, 对拍跳过')
    print('A6 总判定:', 'PASS' if fails == 0 else 'FAIL (%d 锚)' % fails)
    sys.exit(0 if fails == 0 else 1)

if __name__ == '__main__':
    main()
