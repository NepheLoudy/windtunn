#!/usr/bin/env bash
# T1 vs T0 同点对照 (21,-15,-15) — T1 质量首检
T0=~/sweep_t0v2/t0_table.csv
T1=~/sweep_t1/t1_table.csv
python3 << PYEOF
t0 = {}
for l in open("$T0"):
    l = l.strip()
    if not l or l.startswith("#") or l.startswith("V,"):
        continue
    p = l.split(",")
    t0[(p[0], p[1], p[2])] = [float(x) for x in p[6:12]]
names = ["CL", "CD", "Cm", "CY", "Cl", "Cn"]
for key in ("21.0000,-15.0000,-15.0000", "20.0000,-15.0000,-15.0000"):
    for src, tbl in (("T0", "$T0"), ("T1", "$T1")):
        found = None
        for l in open(tbl):
            ls = l.strip()
            if ls.startswith(key + ","):
                found = [float(x) for x in ls.split(",")[6:12]]
                break
        if found:
            print(f"{src} {key}: CL={found[0]:+.4f} CD={found[1]:.4f} Cm={found[2]:+.4f} CY={found[3]:+.4f} Cn={found[5]:+.4f}")
        else:
            print(f"{src} {key}: not-in-table")
PYEOF
