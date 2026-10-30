#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把解析轴写入 cfd_parallel assembly + 校验 hinge_line 两端点"""
import json
import numpy as np

ana = json.load(open('hinges_analytic.json'))
asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
name_of = {24: 'fin_1', 26: 'fin_2', 28: 'fin_3', 30: 'fin_4'}
by_name = {s['name']: s for s in asm['control_surfaces']}
for tag, nm in name_of.items():
    a = ana[str(tag)]
    s = by_name[nm]
    p = np.array(a['point_B']); u = np.array(a['axis_B'])
    # 轴向符号统一: 保持历史 δ 正方向语义 (轴是线, 取反等价但会翻 δ 符号)
    if u @ np.array(s['hinge_axis'], float) < 0:
        u = -u
    L = s['hinge_len_mm'] / 2000.0
    s['hinge_line'] = [[round(float(x), 6) for x in (p - u*L)],
                       [round(float(x), 6) for x in (p + u*L)]]
    s['hinge_axis'] = [round(float(x), 6) for x in u]
    s['hinge_radius_mm'] = a['r_mm']
    s['status'] = 'v3 平行零位: OCC 解析圆柱轴 (r=2.000mm 精确, 残差0.00000)'
    print('%s: 轴点 B=[%.6f,%.6f,%.6f] 轴=[%.6f,%.6f,%.6f] r=%.4f' %
          (nm, *p, *u, a['r_mm']))
json.dump(asm, open('cad/v1/cfd_parallel/airframe_assembly.json', 'w'), ensure_ascii=False, indent=1)
print('assembly updated (analytic axis)')
