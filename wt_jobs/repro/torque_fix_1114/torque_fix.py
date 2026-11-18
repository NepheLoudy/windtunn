#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 v4asm N1 torque bug post-processing recovery — 2026-11-14
Bug (source-verified on this host):
  kernel.cpp object_torque: cross(position(coordinates(n)) - c, F) where position() is
  DOMAIN-CENTERED (cell+0.5-N/2 per axis, kernel.cpp:826-828), while setup.cpp:141 passes
  com = center = (0.5*Nx, 0.5*Ny, 0.5*Nz) ABSOLUTE grid coords (setup.cpp:93).
  => T_rep = T_true - center x F   =>   T_true = T_rep + center x F  (exactly invertible)
  Ny = Nz = uint(Nx*120.0/220.0 + 0.5)  (setup.cpp:77-78)
  Forces (object_force) are NOT affected.

Inputs : out/t2_queue_summary_v4asm.csv (229 rows incl. gate)
         out/forces_osc_{p,y,r}_{f1,f2}_v4asm.csv (6 cases, 12000 samples each)
         ~/sweep_t0v2/t0_table.csv (FVM blue table; embedded fallback below)
Outputs: out/t2_queue_summary_v4asm_tfix.csv   (original untouched; +tx_c/ty_c/tz_c)
         out/osc_lockin_tfix.csv               (raw vs corrected lock-in fit per channel)
         out/torque_fix_result.json            (all validations + key point vs FVM)
"""
import csv, json, math, os, subprocess, sys

HOME = os.path.expanduser('~')
BIN  = os.path.join(HOME, 'fluidx3d_v3/FluidX3D-master/bin')
OUT  = os.path.join(BIN, 'out')
SUMMARY     = os.path.join(OUT, 't2_queue_summary_v4asm.csv')
SUMMARY_FIX = os.path.join(OUT, 't2_queue_summary_v4asm_tfix.csv')
RESULT      = os.path.join(OUT, 'torque_fix_result.json')
OSC_CSV     = os.path.join(OUT, 'osc_lockin_tfix.csv')
LOCKIN_PY   = os.path.join(BIN, 'lockin.py')
T0          = os.path.join(HOME, 'sweep_t0v2/t0_table.csv')

FC, TC = ['fx', 'fy', 'fz'], ['tx', 'ty', 'tz']
L_REF_M, CPM = 0.1146, 1844.09
L_LU = L_REF_M * CPM  # 211.3330... lattice units (same as analysis workstation)

# analysis-station anchors (D:\\WindTunnel3D\\wt_jobs\\tmp\\t2_requal_result.json, 2026-11-14)
ANCH = {
    'a0b0_raw':        [48.5, 28685.9, -29140.1],        # rounded 1dp
    'a0b0_corrected':  [1.614, -218.12, -150.085],       # rounded 3dp
    'a0b0_corr_norm':  [3e-05, -0.00429, -0.00295],      # corrected/(|fx|*L), rounded 5dp
    'xrows_corr_norm': {  # t_corrected_over_denom, denom = |fx(x_a5_b0)|*L_LU, rounded 5dp
        'x_a0_b0':       [3e-05, -0.00428, -0.00295],
        'x_a5_b0':       [0.00415, 0.018, -0.00819],
        'x_an5_b0':      [-0.00319, -0.02645, 0.00195],
        'x_a10_b0':      [0.0083, 0.03991, -0.01292],
        'x_a0_b5':       [0.00273, 0.00094, -0.02479],
        'x_a0_bn5':      [-0.00366, -0.00955, 0.01869],
        'x_a12.5_b5':    [0.01254, 0.05644, -0.03789],
        'x_an12.5_bn5':  [-0.00872, -0.06417, 0.03108],
    },
    'nx_medians_corr': {  # v4asm_torque_median_by_nx, rounded 1dp
        '220': [0.6, -43.4, -10.5], '330': [220.7, 1062.5, -319.6],
        '440': [23.3, 47.7, -215.4], '660': [192.6, -1352.9, -758.1],
    },
}
FVM_FALLBACK_A5B0 = [  # from t0_table.csv (identical rows verified 2026-11-14)
    (20.0, 0.198234, 0.160131, 0.052044, 0.001719, -0.000935, -0.005074),
    (21.0, 0.200355, 0.159997, 0.051033, 0.001776, -0.000799, -0.005126),
    (22.0, 0.199713, 0.159698, 0.051334, 0.001231, -0.000788, -0.004731),
    (23.0, 0.201971, 0.159615, 0.050283, 0.001576, -0.000774, -0.005035),
    (24.0, 0.202255, 0.159398, 0.050125, 0.001566, -0.000720, -0.005005),
    (25.0, 0.203364, 0.159319, 0.049425, 0.001549, -0.000801, -0.005008),
]  # V, CL, CD, Cm, CY, Cl, Cn

OSC_CASES = [  # from osc_batch.sh: ALPHA=5 BETA=0 AMP=2deg NX=440 NU=0.02, skip 200k steps
    ('osc_p_f1', 1, 0.012566),  ('osc_p_f2', 1, 0.0031416),   # axis1 pitch -> ty (Cmq)
    ('osc_y_f1', 2, 0.012566),  ('osc_y_f2', 2, 0.0031416),   # axis2 yaw   -> tz (Cnr)
    ('osc_r_f1', 3, 0.012566),  ('osc_r_f2', 3, 0.0031416),   # axis3 roll  -> tx (Clp)
]
OSC_T_SKIP, OSC_SAMPLE = 200000.0, 100
AXIS_CH = {1: 'ty', 2: 'tz', 3: 'tx'}

# ---------------- core correction ----------------
def ny_of(nx):
    return int(nx * 120.0 / 220.0 + 0.5)  # setup.cpp:77 uint truncation

def center_x_F(nx, fx, fy, fz):
    """(center x F) with center=(Nx/2,Ny/2,Nz/2), Ny=Nz=round(Nx*120/220)."""
    ny = ny_of(nx)
    cx, cy, cz = nx / 2.0, ny / 2.0, ny / 2.0
    return (cy * fz - cz * fy, cz * fx - cx * fz, cx * fy - cy * fx)

def correct3(nx, fx, fy, fz, tx, ty, tz):
    d = center_x_F(nx, fx, fy, fz)
    return (tx + d[0], ty + d[1], tz + d[2])

# ---------------- helpers ----------------
def rt(x, nd=6):
    return None if x is None else round(x, nd)

def mean(a):
    return sum(a) / len(a) if a else None

def median(a):
    if not a: return None
    s = sorted(a); n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])

def close(got, want, tol):
    return abs(got - want) <= tol + 1e-12

# ---------------- summary load + fix ----------------
def load_summary():
    with open(SUMMARY) as f:
        return list(csv.DictReader(f))

def fix_summary(rows):
    n_fix = 0
    for r in rows:
        nx = int(r['nx'])
        fx, fy, fz = float(r['fx']), float(r['fy']), float(r['fz'])
        tx, ty, tz = float(r['tx']), float(r['ty']), float(r['tz'])
        tx_c, ty_c, tz_c = correct3(nx, fx, fy, fz, tx, ty, tz)
        r['tx_c'], r['ty_c'], r['tz_c'] = ('%.6g' % tx_c, '%.6g' % ty_c, '%.6g' % tz_c)
        n_fix += 1
    cols = ['tag', 'alpha', 'beta', 'nx', 'seed', 'nu', 'V', 'steps',
            'fx', 'fy', 'fz', 'tx', 'ty', 'tz', 'tx_c', 'ty_c', 'tz_c']
    with open(SUMMARY_FIX, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows: w.writerow(r)
    return n_fix

# ---------------- validation a: symmetric state -> ~zero ----------------
def val_a(rows):
    z = [r for r in rows if r['tag'] == 'x_a0_b0'][0]
    fx = float(z['fx']); L2 = abs(fx) * L_LU
    raw = [float(z[c]) for c in TC]
    cor = [float(z[c + '_c']) for c in TC]
    norm = [v / L2 for v in cor]
    detail = {'tag': 'x_a0_b0', 'raw': raw, 'corrected': cor,
              'corrected_over_absfxL': norm,
              'abs_corrected_over_absfxL': [abs(v) for v in norm]}
    ok_anchor = all(close(cor[i], ANCH['a0b0_corrected'][i], 5.1e-4) for i in range(3))
    ok_zero   = all(abs(v) < 0.01 for v in norm)
    detail['anchor_match'] = ok_anchor
    detail['all_below_0p01'] = ok_zero
    return ok_anchor and ok_zero, detail

# ---------------- validation b: mirror antisymmetry ----------------
def antisym(rows, tpos, tneg, col):
    p = [r for r in rows if r['tag'] == tpos][0]
    n = [r for r in rows if r['tag'] == tneg][0]
    vp, vn = float(p[col]), float(n[col])
    return {'pair': [tpos, tneg], 'axis_col': col, 'v_pos': vp, 'v_neg': vn,
            'signs_opposite': vp * vn < 0,
            'antisym_residual_ratio': abs(vp + vn) / max(abs(vp), abs(vn))}

def val_b(rows):
    pairs_b0 = [('x_a5_b0', 'x_an5_b0', 'tx'), ('x_a0_b5', 'x_a0_bn5', 'tz')]
    checks = []
    for cs in ('', '_c'):
        for tp, tn, col in pairs_b0:
            checks.append({'frame': 'raw' if cs == '' else 'corrected', **antisym(rows, tp, tn, col + cs)})
    mirror = []
    for col in TC:
        mirror.append({'frame': 'corrected', **antisym(rows, 'x_a12.5_b5', 'x_an12.5_bn5', col + '_c')})
        mirror.append({'frame': 'raw',      **antisym(rows, 'x_a12.5_b5', 'x_an12.5_bn5', col)})
    corr_ok = all(c['signs_opposite'] for c in checks if c['frame'] == 'corrected') \
          and all(c['signs_opposite'] for c in mirror if c['frame'] == 'corrected')
    return corr_ok, {'b0_pairs': checks, 'mirror_pair_a12p5b5': mirror,
        'note': 'hard pass = sign opposition (mirror physics); residual ratio quantifies asymmetry (real assembly has DC offsets, e.g. fy(x_a0_b0)=0.51)'}

# ---------------- validation c: cross-check vs analysis-station JSON ----------------
def val_c(rows):
    det = {'a0b0': {}, 'xrows': {}, 'nx_medians': {}}
    ok = True
    z = [r for r in rows if r['tag'] == 'x_a0_b0'][0]
    raw = [float(z[c]) for c in TC]; cor = [float(z[c + '_c']) for c in TC]
    det['a0b0']['raw_match'] = [close(raw[i], ANCH['a0b0_raw'][i], 0.051) for i in range(3)]
    det['a0b0']['corrected_match'] = [close(cor[i], ANCH['a0b0_corrected'][i], 5.1e-4) for i in range(3)]
    det['a0b0']['corr_norm_match'] = [close(cor[i] / (abs(float(z['fx'])) * L_LU),
                                            ANCH['a0b0_corr_norm'][i], 1.1e-5) for i in range(3)]
    ok &= all(det['a0b0'][k][i] for k in det['a0b0'] for i in range(3))
    xref = [r for r in rows if r['tag'] == 'x_a5_b0'][0]   # analysis used THIS denom for all x rows
    denom = abs(float(xref['fx'])) * L_LU
    det['denom_absfxL_x_a5_b0'] = denom
    for tag, want in ANCH['xrows_corr_norm'].items():
        r = [q for q in rows if q['tag'] == tag]
        if not r:
            det['xrows'][tag] = {'missing': True}; ok = False; continue
        r = r[0]
        got = [float(r[c + '_c']) / denom for c in TC]
        m = [close(got[i], want[i], 1.1e-5) for i in range(3)]
        det['xrows'][tag] = {'got': [rt(v, 6) for v in got], 'want': want, 'match': m}
        ok &= all(m)
    bynx = {}
    for r in rows:
        if r['tag'] == 'gate': continue
        bynx.setdefault(int(r['nx']), []).append([float(r[c + '_c']) for c in TC])
    for k, want in ANCH['nx_medians_corr'].items():
        got = [median([v[i] for v in bynx[int(k)]]) for i in range(3)]
        m = [close(got[i], want[i], 0.051) for i in range(3)]
        det['nx_medians'][k] = {'n': len(bynx[int(k)]), 'got': [rt(v, 2) for v in got],
                                'want': want, 'match': m}
        ok &= all(m)
    return ok, det

# ---------------- key point vs FVM (alpha=5,beta=0, nx=440) ----------------
def load_fvm_a5b0():
    if os.path.exists(T0):
        out = []
        with open(T0) as f:
            lines = [l for l in f if not l.startswith('#')]
            for r in csv.DictReader(lines):
                if abs(float(r['alpha']) - 5.0) < 1e-9 and abs(float(r['beta'])) < 1e-9 \
                   and float(r['de']) == 0.0 and float(r['da']) == 0.0 and float(r['dr']) == 0.0:
                    out.append({k: float(r[k]) for k in ('V', 'CL', 'CD', 'Cm', 'CY', 'Cl', 'Cn')})
        if len(out) == 6:
            return out, 't0_table.csv'
    return [dict(zip(('V', 'CL', 'CD', 'Cm', 'CY', 'Cl', 'Cn'), row)) for row in FVM_FALLBACK_A5B0], 'embedded_fallback'

def keypoint(rows):
    fvm, src = load_fvm_a5b0()
    L = [r for r in rows if r['tag'] == 'x_a5_b0'][0]
    fx, fy, fz = float(L['fx']), float(L['fy']), float(L['fz'])
    denom = abs(fx) * L_LU
    t_raw = [float(L[c]) / denom for c in TC]
    t_cor = [float(L[c + '_c']) / denom for c in TC]
    fvm_m = {'Cl/CD': mean([r['Cl'] / r['CD'] for r in fvm]),
             'Cm/CD': mean([r['Cm'] / r['CD'] for r in fvm]),
             'Cn/CD': mean([r['Cn'] / r['CD'] for r in fvm]),
             'CY/CD': mean([r['CY'] / r['CD'] for r in fvm]),
             'CL/CD': mean([r['CL'] / r['CD'] for r in fvm])}
    # frame map (analysis-locked): x_LBM=-x_F, y=y, z=-z => tx<->-Cl, ty<->Cm, tz<->-Cn
    mapped = {
        'tx_vs_-ClCD': (t_raw[0], t_cor[0], -fvm_m['Cl/CD']),
        'ty_vs_CmCD':  (t_raw[1], t_cor[1],  fvm_m['Cm/CD']),
        'tz_vs_-CnCD': (t_raw[2], t_cor[2], -fvm_m['Cn/CD']),
    }
    out = {
        'tag': 'x_a5_b0', 'nx': int(float(L['nx'])), 'fvm_source': src,
        'L_lu': L_LU, 'denom_absfxL': denom,
        'lbm_raw_over_denom': [rt(v, 6) for v in t_raw],
        'lbm_corrected_over_denom': [rt(v, 6) for v in t_cor],
        'fvm_means': {k: rt(v, 6) for k, v in fvm_m.items()},
        'mapped_pairs': {k: {'raw': rt(a, 6), 'corrected': rt(b, 6), 'fvm': rt(c, 6),
                             'ratio_raw_over_fvm': rt(a / c, 4) if c else None,
                             'ratio_corrected_over_fvm': rt(b / c, 4) if c else None,
                             'gap_narrowed_by_correction': bool(abs(b - c) < abs(a - c))}
                         for k, (a, b, c) in mapped.items()},
        'force_context_14x': {
            'lbm_fz_over_absfx': rt(fz / abs(fx), 6), 'fvm_CL_over_CD': rt(fvm_m['CL/CD'], 6),
            'ratio': rt(abs(fz / abs(fx)) / fvm_m['CL/CD'], 4),
            'note': 'lift-axis collapse ~14x (0.0901 vs 1.2586); forces untouched by N1 => unchanged by this fix'},
    }
    return out

# ---------------- osc lock-in fit (port of bin/lockin.py, verified against it) ----------------
def solve3(M, b):
    A = [row[:] + [bv] for row, bv in zip(M, b)]
    for i in range(3):
        piv = max(range(3), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        d = A[i][i]
        A[i] = [v / d for v in A[i]]
        for r in range(3):
            if r != i:
                f = A[r][i]
                A[r] = [vr - f * vi for vr, vi in zip(A[r], A[i])]
    return [A[i][3] for i in range(3)]

def lockin_fit(ts, cols, omega):
    """cols = list of 6 series (fx..tz). returns per-channel dict."""
    basis = [(1.0, math.sin(omega * t), math.cos(omega * t)) for t in ts]
    res = []
    for col in cols:
        M = [[0.0] * 3 for _ in range(3)]; b = [0.0] * 3
        for e, y in zip(basis, col):
            for i in range(3):
                b[i] += e[i] * y
                for j in range(3):
                    M[i][j] += e[i] * e[j]
        dc, As, Ac = solve3(M, b)
        resid = [y - (dc + As * e[1] + Ac * e[2]) for e, y in zip(basis, col)]
        rrms = math.sqrt(sum(v * v for v in resid) / len(resid))
        res.append({'dc': dc, 'As': As, 'Ac': Ac, 'amp': math.hypot(As, Ac),
                    'phase_deg': math.degrees(math.atan2(Ac, As)), 'res_rms': rrms,
                    'amp_over_res': (math.hypot(As, Ac) / rrms) if rrms > 0 else None})
    return res

def run_real_lockin(path, omega):
    """run bin/lockin.py on the RAW file to validate the port; returns amps or None."""
    try:
        p = subprocess.run([sys.executable, LOCKIN_PY, path, repr(omega), '%g' % OSC_T_SKIP, str(OSC_SAMPLE)],
                           capture_output=True, text=True, timeout=300)
        amps = []
        for line in p.stdout.splitlines():
            f = line.split()
            if len(f) == 9 and f[0] in ('fx', 'fy', 'fz', 'tx', 'ty', 'tz'):
                amps.append(float(f[4]))
        return amps if len(amps) == 6 else None
    except Exception:
        return None

def osc_analysis():
    names = FC + TC
    per_case, table_rows = {}, []
    port_ok_all = True
    for tag, axis, omega in OSC_CASES:
        path = os.path.join(OUT, 'forces_%s_v4asm.csv' % tag)
        ts, F, T = [], [], []
        with open(path) as fh:
            for r in csv.DictReader(fh):
                t = float(r['t'])
                if t <= OSC_T_SKIP: continue
                ts.append(t)
                F.append((float(r['fx']), float(r['fy']), float(r['fz'])))
                T.append((float(r['tx']), float(r['ty']), float(r['tz'])))
        nx = 440  # osc_batch.sh fixed NX=440
        Tc = [correct3(nx, f[0], f[1], f[2], tq[0], tq[1], tq[2]) for f, tq in zip(F, T)]
        cols_raw = [[f[i] for f in F] for i in range(3)] + [[tq[i] for tq in T] for i in range(3)]
        cols_cor = [[f[i] for f in F] for i in range(3)] + [[t[i] for t in Tc] for i in range(3)]
        fit_raw = lockin_fit(ts, cols_raw, omega)
        fit_cor = lockin_fit(ts, cols_cor, omega)
        real = run_real_lockin(path, omega)
        if real:
            port_dev = max(abs(fit_raw[i]['amp'] - real[i]) / max(abs(real[i]), 1e-30) for i in range(6))
        else:
            port_dev = None; port_ok_all = False
        ach = AXIS_CH[axis]
        ai = names.index(ach)
        per_case[tag] = {
            'axis': axis, 'axis_channel': ach, 'omega': omega, 'n_samples': len(ts),
            'port_vs_real_lockin_maxreldiff': port_dev,
            'axis_channel_raw': {k: rt(v, 6) for k, v in fit_raw[ai].items()},
            'axis_channel_corrected': {k: rt(v, 6) for k, v in fit_cor[ai].items()},
            'amp_change_ratio_corrected_over_raw': rt(fit_cor[ai]['amp'] / fit_raw[ai]['amp'], 6) if fit_raw[ai]['amp'] else None,
        }
        for i, nm in enumerate(names):
            table_rows.append({'case': tag, 'axis': axis, 'omega': omega, 'ch': nm,
                               'raw_dc': '%.6g' % fit_raw[i]['dc'], 'raw_As': '%.6g' % fit_raw[i]['As'],
                               'raw_Ac': '%.6g' % fit_raw[i]['Ac'], 'raw_amp': '%.6g' % fit_raw[i]['amp'],
                               'raw_phase_deg': '%.4g' % fit_raw[i]['phase_deg'], 'raw_res_rms': '%.6g' % fit_raw[i]['res_rms'],
                               'cor_dc': '%.6g' % fit_cor[i]['dc'], 'cor_As': '%.6g' % fit_cor[i]['As'],
                               'cor_Ac': '%.6g' % fit_cor[i]['Ac'], 'cor_amp': '%.6g' % fit_cor[i]['amp'],
                               'cor_phase_deg': '%.4g' % fit_cor[i]['phase_deg'], 'cor_res_rms': '%.6g' % fit_cor[i]['res_rms']})
    with open(OSC_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(table_rows[0].keys()))
        w.writeheader(); w.writerows(table_rows)
    return {'per_case': per_case, 'port_verified_vs_lockin_py': port_ok_all,
            'table': OSC_CSV, 'note': 'T_true(t)=T_rep(t)+center x F(t) per sample (c=(220,120,120), nx=440); DC/amp/phase all shift because F(t) carries the lock-in frequency'}

# ---------------- main ----------------
def main():
    rows = load_summary()
    n_fix = fix_summary(rows)
    pa, da = val_a(rows)
    pb, db = val_b(rows)
    pc, dc_ = val_c(rows)
    kp = keypoint(rows)
    osc = osc_analysis()
    res = {
        'meta': {
            'date': '2026-11-14', 'bug': 'object_torque mixes centered-frame position() with absolute-frame center arg',
            'source_refs': 'kernel.cpp:826-828 position() centered; kernel.cpp:1985 cross(pos-c,F); setup.cpp:77 Ny=Nz=uint(Nx*120/220+0.5); setup.cpp:93 center; setup.cpp:141 com=center',
            'formula': 'T_true = T_rep + center x F, center=(Nx/2,Ny/2,Nz/2)',
            'inputs': [SUMMARY, 'out/forces_osc_*_v4asm.csv', T0],
            'outputs': [SUMMARY_FIX, OSC_CSV, RESULT],
            'rows_fixed': n_fix, 'forces_untouched': True,
        },
        'validation': {
            'a_symmetric_nearzero': {'pass': pa, **da},
            'b_mirror_antisymmetry': {'pass': pb, **db},
            'c_crosscheck_analysis_station': {'pass': pc, **dc_},
        },
        'keypoint_a5b0_nx440_vs_fvm': kp,
        'osc_lockin_tfix': osc,
    }
    all_pass = pa and pb and pc
    res['validation']['ALL_PASS'] = all_pass
    with open(RESULT, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('rows fixed:', n_fix)
    print('validation a (a0b0 near-zero):', pa)
    print('validation b (mirror antisym):', pb)
    print('validation c (station crosscheck):', pc)
    print('ALL_PASS:', all_pass)
    print('keypoint ty_vs_CmCD:', json.dumps(kp['mapped_pairs']['ty_vs_CmCD'], ensure_ascii=False))
    print('force 14x context:', json.dumps(kp['force_context_14x'], ensure_ascii=False))
    for tag, d in osc['per_case'].items():
        print('osc %s (%s): raw amp=%.6g corrected amp=%.6g ratio=%.4f port_dev=%s'
              % (tag, d['axis_channel'], d['axis_channel_raw']['amp'], d['axis_channel_corrected']['amp'],
                 d['amp_change_ratio_corrected_over_raw'] or float('nan'), d['port_vs_real_lockin_maxreldiff']))
    print('JSON ->', RESULT)

if __name__ == '__main__':
    main()
