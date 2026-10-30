#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轴符号硬写回历史约定 + 重建下游 (dart / dashboard mesh) 检查清单"""
import json
import numpy as np

SIGN = {  # 与最初 assembly 一致的 δ 正方向语义
    'fin_1': [0.0, 0.707107, 0.707107],
    'fin_2': [0.0, 0.707107, -0.707107],
    'fin_3': [0.0, -0.707107, -0.707107],
    'fin_4': [0.0, -0.707107, 0.707107],
}
asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
for s in asm['control_surfaces']:
    u = np.array(SIGN[s['name']])
    p = 0.5 * (np.array(s['hinge_line'][0]) + np.array(s['hinge_line'][1]))
    L = s['hinge_len_mm'] / 2000.0
    s['hinge_axis'] = [round(float(x), 6) for x in u]
    s['hinge_line'] = [[round(float(x), 6) for x in (p - u*L)],
                       [round(float(x), 6) for x in (p + u*L)]]
    print('%s: axis=%s point=[%.6f,%.6f,%.6f]' % (s['name'], s['hinge_axis'], *p))
json.dump(asm, open('cad/v1/cfd_parallel/airframe_assembly.json', 'w'), ensure_ascii=False, indent=1)
print('sign convention restored')
