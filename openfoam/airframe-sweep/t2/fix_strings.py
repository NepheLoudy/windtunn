#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复算力节点 setup.cpp 中被 heredoc 吃掉转义的 fprintf 字符串"""
path = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
s = open(path, encoding="utf-8").read()

# 断行字符串 1: fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");
s = s.replace('fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");',
              'fprintf(f, "t,fx,fy,fz,tx,ty,tz\\n");')
# 断行字符串 2: fprintf(g, "%u,...,%.6g\n");
s = s.replace('fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n");',
              'fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\\n");')

open(path, "w", encoding="utf-8").write(s)
# 验证: 不再存在"fprintf 行末无引号"模式
bad = 0
for i, line in enumerate(s.split("\n"), 1):
    if "fprintf" in line and line.rstrip().endswith('tz') or \
       "fprintf" in line and line.rstrip().endswith('%.6g'):
        bad += 1
print(f"patched, broken-pattern count = {bad}")
