import sys

p = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
s = open(p).read()
patch = open("/tmp/setup_dart_v2.cpp", encoding="utf-8").read()
lines = s.splitlines(keepends=True)
start = end = None
for i, ln in enumerate(lines):
    if "void main_setup() { // dart" in ln and start is None:
        start = i
    if start is not None and "#endif // DART" in ln:
        end = i
        break
assert start is not None and end is not None, (start, end)
new = lines[:start] + [patch] + ["\n", "#endif // DART // v2\n"] + lines[end+1:]
open(p, "w").write(new)
print("spliced v2: lines %d-%d replaced" % (start+1, end+1))
