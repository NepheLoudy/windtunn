# -*- coding: utf-8 -*-
"""扫气覆盖矩阵 vs 笛卡尔积: 缺哪些格"""
import csv, itertools
rows = [r for r in csv.DictReader(l for l in open(r'C:/Users/nebula/AppData/Local/Temp/master_test.csv', encoding='utf-8') if not l.startswith('#'))]
print('rows', len(rows))
dims = {}
for i, k in enumerate(('V','alpha','beta','de','da','dr')):
    dims[k] = sorted({float(r[k]) for r in rows})
    print(k, dims[k])
have = {(float(r['V']),float(r['alpha']),float(r['beta']),float(r['de']),float(r['da']),float(r['dr'])) for r in rows}
missing = []
for combo in itertools.product(dims['V'], dims['alpha'], dims['beta'], dims['de'], dims['da'], dims['dr']):
    if combo not in have:
        missing.append(combo)
print('missing', len(missing))
from collections import Counter
c = Counter()
for m in missing:
    for i, k in enumerate(('V','alpha','beta','de','da','dr')):
        c[k] += 0
# 按缺格模式归类: 哪些 (V,α) 组合缺
by_va = Counter((m[0], m[1]) for m in missing)
print('缺格 (V,α) 分布 top10:', by_va.most_common(10))
b_beta = Counter(m[2] for m in missing)
print('按 β 分布:', dict(b_beta))
