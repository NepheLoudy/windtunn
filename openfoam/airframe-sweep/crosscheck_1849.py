#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""surf1849 终局交叉验证: scipy 轴 vs 旧轴, 独立第三实现算径向分布"""
import json
import numpy as np
import gmsh

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge('cad/v1/airframe.step')
gmsh.model.occ.synchronize()
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.35)
gmsh.model.mesh.generate(2)
atags, axyz, _ = gmsh.model.mesh.getNodes(2, 1849, includeBoundary=True)
P = np.array(axyz).reshape(-1, 3)
gmsh.finalize()

h = json.load(open('hinges_scipy.json'))
bf = h['24']['band_fit']
# B 系米制 → STEP mm: x = z_B*1000 - 0.1 ; y = y_B*1000 + 0.2 ; z = -x_B*1000 + 105.5
c = np.array([bf['center_B'][2]*1000 - 0.1, bf['center_B'][1]*1000 + 0.2, -bf['center_B'][0]*1000 + 105.5])
u = np.array([-bf['axis_B'][2], bf['axis_B'][1], bf['axis_B'][0]])
u = u / np.linalg.norm(u)
V = P - c
t = V @ u
rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
print('scipy轴 独立复算: r min=%.3f med=%.3f max=%.3f std=%.4f' %
      (rad.min(), np.median(rad), rad.max(), rad.std()))

o = [h2 for h2 in json.load(open('cad/v1/hinges.json')) if h2['part_tag'] == 24][0]
c0 = np.array(o['center_mm'])
a0 = np.array(o['axis']); a0 = a0 / np.linalg.norm(a0)
V = P - c0
t = V @ a0
rad0 = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
print('旧轴   独立复算: r min=%.3f med=%.3f max=%.3f std=%.4f' %
      (rad0.min(), np.median(rad0), rad0.max(), rad0.std()))
