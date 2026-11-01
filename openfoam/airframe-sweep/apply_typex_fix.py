import sys

p = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
s = open(p).read()
old = ('\tparallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);\n'
       '\t\tif(lbm.flags[n]!=TYPE_S)')
new = ('\tparallel_for(lbm.get_N(), [&](ulong n) { uint x=0u, y=0u, z=0u; lbm.coordinates(n, x, y, z);\n'
       '\t\tif(lbm.flags[n]==TYPE_S) lbm.flags[n] = TYPE_S|TYPE_X; '
       '// force summation exact-matches TYPE_S|TYPE_X (official Stokes example); voxelize_stl only sets TYPE_S -> force was identically zero (fixed 11-01)\n'
       '\t\tif(lbm.flags[n]!=TYPE_S)')
assert old in s, "anchor not found"
s = s.replace(old, new, 1)
open(p, "w").write(s)
print("TYPE_X fix applied")
