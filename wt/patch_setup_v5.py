#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup.cpp DART 块 v5 补丁: 单一 body.stl → 逐件体素化 (26 body + 4 平行舵)
在 qianli 上执行: python3 patch_setup_v5.py
"""
p = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
t = open(p).read()
old = '\tlbm.voxelize_stl(get_exe_path()+"cfd_new/body.stl", center, cpm, TYPE_S);'
assert old in t, "anchor missing"
new = (
    "\t// v5: per-piece voxelization (26 body + 4 parallel fins) — concat-STL ray\n"
    "\t// voxelization misjudges interpenetrating shells (fz -122 lesson, 10-30)\n"
    "\tfor (int i = 1; i <= 26; i++) {\n"
    "\t\tchar buf[128];\n"
    '\t\tsnprintf(buf, sizeof(buf), "cfd_new/body_%02d.stl", i);\n'
    "\t\tlbm.voxelize_stl(get_exe_path()+buf, center, cpm, TYPE_S);\n"
    "\t}\n"
    "\tfor (int i = 1; i <= 4; i++) {\n"
    "\t\tchar buf[128];\n"
    '\t\tsnprintf(buf, sizeof(buf), "cfd_new/fin_%d.stl", i);\n'
    "\t\tlbm.voxelize_stl(get_exe_path()+buf, center, cpm, TYPE_S);\n"
    "\t}"
)
t = t.replace(old, new)
open(p, "w").write(t)
print("setup.cpp v5 written")
