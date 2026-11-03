# -*- coding: utf-8 -*-
"""E4: lookup_aero × 蓝表集成测试 v3 (2026-11-03)
正确口径: lookup_aero 返回 (F_B, M_B) 牛顿 — 系数×q̄S。测试走系数往返:
手工 coeffs() 直查 vs 表行值 (恒等) + V 插值 + 出域 clamp + 单值维度。
出全后全表重跑本脚本即可 (迷你表→全表只换 SRC)。
"""
import csv, math, sys, warnings
import numpy as np
sys.path.insert(0, r'D:/WindTunnelSuite/guidance_sim/aero')
import lookup_aero as la

SRC = r'C:/Users/nebula/AppData/Local/Temp/master_test.csv'
fails = []
def check(name, cond, detail=''):
    print(('  OK  ' if cond else '  FAIL'), name, detail)
    if not cond: fails.append(name)

rows = [r for r in csv.DictReader(l for l in open(SRC, encoding='utf-8') if not l.startswith('#'))]
sub = [r for r in rows if float(r['alpha']) in (-15.0, -12.5, -10.0)]  # 已完成剖面
meta = [l for l in open(SRC, encoding='utf-8') if l.startswith('#')]
T = r'C:/Users/nebula/AppData/Local/Temp/master_mini.csv'
with open(T, 'w', encoding='utf-8', newline='') as f:
    f.writelines(meta)
    w = csv.writer(f)
    w.writerow(['V','alpha','beta','de','da','dr','CL','CD','Cm','CY','Cl','Cn'])
    for r in sub:
        w.writerow([r[k] for k in ('V','alpha','beta','de','da','dr','CL','CD','Cm','CY','Cl','Cn')])
print('迷你表: %d 行 (α∈{-15,-12.5,-10} 完整剖面)' % len(sub))

# 1) 吃表 + 笛卡尔积完整性
t = la.load_table(T)
print('1) load_table OK')

# 2) 角点恒等: coeffs() 直查表节点 = 表行值
maxerr = 0.0
for r in sub:
    c = t.coeffs(float(r['V']), float(r['alpha']), float(r['beta']), 0.0, 0.0, 0.0)
    exp = [float(r[col]) for col in ('CL','CD','Cm','CY','Cl','Cn')]
    got = [c['CL'], c['CD'], c['Cm'], c['CY'], c['Cl'], c['Cn']]
    maxerr = max(maxerr, max(abs(g-e) for g, e in zip(got, exp)))
check('2) 角点恒等 (%d 行全采)' % len(sub), maxerr < 5e-4, 'max|Δ|=%.2e' % maxerr)

# 3) V 维中点插值 = 两档均值 (同姿态)
lo = next(r for r in sub if float(r['V'])==15.0 and float(r['alpha'])==-15.0 and float(r['beta'])==-15.0)
hi = next(r for r in sub if float(r['V'])==20.0 and float(r['alpha'])==-15.0 and float(r['beta'])==-15.0)
c = t.coeffs(17.5, -15.0, -15.0, 0.0, 0.0, 0.0)
exp = [(float(lo[col]) + float(hi[col]))/2 for col in ('CL','CD','Cm','CY','Cl','Cn')]
got = [c['CL'], c['CD'], c['Cm'], c['CY'], c['Cl'], c['Cn']]
err = max(abs(g-e) for g, e in zip(got, exp))
check('3) V 中点插值=两档均值', err < 1e-3, 'max|Δ|=%.2e' % err)

# 4) 全链出口: lookup_aero → F_B 量级 sanity (q̄S×CD 量级)
F, M = la.lookup_aero(15.0, -15.0, -15.0, 0.0, 0.0, 0.0, table=t)
qS = 0.5*1.225*15.0**2*0.010306121
cd = float(lo['CD'])
check('4) F 模长 ~ q̄S×|C| 量级', 0.2*qS < np.linalg.norm(F) < 2.0*qS,
      '|F|=%.3f qS=%.3f CD=%.3f' % (np.linalg.norm(F), qS, cd))
check('4b) F/M 全有限', bool(np.isfinite(F).all() and np.isfinite(M).all()))

# 5) 出域 clamp + 警告
with warnings.catch_warnings(record=True) as wlist:
    warnings.simplefilter('always')
    F2, M2 = la.lookup_aero(22.0, 99.0, 0, 0, 0, 0, table=t)
check('5) 出域 clamp 触发警告', len(wlist) > 0, 'warnings=%d' % len(wlist))
check('5b) 出域值有限', bool(np.isfinite(F2).all() and np.isfinite(M2).all()))

# 6) 全单值维度表 (10-31 修的雷: 每维 len==1)
T1 = T + '.single'
with open(T1, 'w', encoding='utf-8', newline='') as f:
    f.writelines(meta)
    w = csv.writer(f)
    w.writerow(['V','alpha','beta','de','da','dr','CL','CD','Cm','CY','Cl','Cn'])
    w.writerow([20.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.01, 0.0, 0.001, 0.002])
F3, M3 = la.lookup_aero(20.0, 0.0, 0.0, 0.0, 0.0, 0.0, table=la.load_table(T1))
check('6) 全单值维度不炸且有限', bool(np.isfinite(F3).all() and np.isfinite(M3).all()))

print()
print('FAILS:', fails if fails else '无 — 全过')
sys.exit(1 if fails else 0)
