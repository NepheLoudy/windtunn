import sys

p = "/home/qianli/fluidx3d_v3/FluidX3D-master/src/setup.cpp"
s = open(p).read()
old = "\tconst float alpha_deg = 12.5f, beta_deg = 0.0f;"
new = ("\tconst char* a_env = getenv(\"ALPHA\"); const char* b_env = getenv(\"BETA\");\n"
       "\tconst float alpha_deg = a_env ? (float)atof(a_env) : 12.5f;\n"
       "\tconst float beta_deg = b_env ? (float)atof(b_env) : 0.0f;")
assert old in s, "alpha anchor not found"
s = s.replace(old, new, 1)
open(p, "w").write(s)
print("ALPHA/BETA env applied")
