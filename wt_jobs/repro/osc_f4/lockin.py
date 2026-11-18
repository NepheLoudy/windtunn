#!/usr/bin/env python3
# lockin.py -- F4 forced-oscillation lock-in regressor (pure stdlib, no numpy)
# usage: python3 lockin.py <forces.csv> <omega_rad_per_step> <t_skip> [sample_step]
# fits y(t) = DC + As*sin(w t) + Ac*cos(w t) per column via 3x3 normal equations,
# reports in-phase (As) / quadrature (Ac) components, amplitude, residual RMS,
# and sinc-corrected amplitude (zero-order-hold attenuation of the stepped inlet drive).
import sys, math

csv_path, omega, t_skip = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
sample = int(sys.argv[4]) if len(sys.argv) > 4 else 100

rows = []
with open(csv_path) as fh:
    next(fh)  # header
    for line in fh:
        p = line.strip().split(',')
        if len(p) == 7:
            rows.append([float(v) for v in p])
rows = [r for r in rows if r[0] > t_skip]
names = ['fx', 'fy', 'fz', 'tx', 'ty', 'tz']

def solve3(M, b):  # gaussian elim, 3x3
    A = [row[:] + [bv] for row, bv in zip(M, b)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        d = A[i][i]
        A[i] = [v / d for v in A[i]]
        for r in range(3):
            if r != i:
                f = A[r][i]
                A[r] = [vr - f * vi for vr, vi in zip(A[r], A[i])]
    return [A[i][3] for i in range(3)]

sinc = math.sin(omega * sample / 2.0) / (omega * sample / 2.0) if omega * sample > 0 else 1.0
print(f"# rows={len(rows)} omega={omega:.6g} t_skip={t_skip:g} sample={sample} sinc_corr=1/{sinc:.4f}")
print(f"# {'ch':>2} {'DC':>12} {'As(sin)':>12} {'Ac(cos)':>12} {'amp':>12} {'phase_deg':>9} {'res_rms':>10} {'amp/res':>8} {'amp_zoh_adj':>12}")
for c in range(6):
    col = [r[c + 1] for r in rows]
    # normal equations for basis [1, sin, cos]
    S = [0.0] * 6  # s1,s2,s3 sums of basis products
    basis = [(1.0, math.sin(omega * r[0]), math.cos(omega * r[0])) for r in rows]
    M = [[0.0] * 3 for _ in range(3)]
    b = [0.0] * 3
    for (e, y) in zip(basis, col):
        for i in range(3):
            b[i] += e[i] * y
            for j in range(3):
                M[i][j] += e[i] * e[j]
    x = solve3(M, b)
    dc, As, Ac = x
    resid = [y - (dc + As * e[1] + Ac * e[2]) for (e, y) in zip(basis, col)]
    rrms = math.sqrt(sum(v * v for v in resid) / len(resid))
    amp = math.hypot(As, Ac)
    print(f"  {names[c]:>2} {dc:12.5g} {As:12.5g} {Ac:12.5g} {amp:12.5g} {math.degrees(math.atan2(Ac, As)):9.2f} {rrms:10.4g} {amp / rrms if rrms > 0 else float('inf'):8.2f} {amp / sinc:12.5g}")
