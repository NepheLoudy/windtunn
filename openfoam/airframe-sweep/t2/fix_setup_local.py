#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 setup_node.cpp 中两处被真换行切断的 fprintf 字符串"""
path = r"D:\WindTunnelSuite\openfoam\airframe-sweep\t2\setup_node.cpp"
s = open(path, encoding="utf-8").read()

# 第一处: fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");
s = s.replace('fprintf(f, "t,fx,fy,fz,tx,ty,tz\n");',
              'fprintf(f, "t,fx,fy,fz,tx,ty,tz\\n");')
# 第二处: fprintf(g, "%u,...,%.6g\n", t+SAMPLE, ...);
s = s.replace('fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n", t+SAMPLE, F.x, F.y, F.z, T.x, T.y, T.z);',
              'fprintf(g, "%u,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\\n", t+SAMPLE, F.x, F.y, F.z, T.x, T.y, T.z);')

open(path, "w", encoding="utf-8", newline="\n").write(s)

bad = [i for i, l in enumerate(s.split("\n"), 1)
       if "fprintf" in l and not l.rstrip().endswith(");")]
print("bad fprintf lines after fix:", bad)
