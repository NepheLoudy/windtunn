#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup.cpp v5→v6 回退: 逐件体素化 → 单一融合体 body.stl (fuse_body v3 已保证无舵)"""
p = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
t = open(p).read()
start = t.find("\t// v5: per-piece voxelization")
end = t.find("\tconst float alpha_deg")
assert start != -1 and end != -1 and start < end, "markers missing"
t = t[:start] + '\tlbm.voxelize_stl(get_exe_path()+"cfd_new/body.stl", center, cpm, TYPE_S);\n' + t[end:]
open(p, "w").write(t)
print("setup.cpp v6 (single fused body) written")
