#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J1: 增量拉表 + 六锚审计 + 生成仪表台数据 — 本机最小任务包的核心

单次执行 2-5 分钟, 幂等, 无常驻。做五件事:
  1. 经 WSL ssh 拉 qianli 的 t0_table.csv / t1_table.csv / sweep.log / forces.csv
  2. 对拉回的蓝表跑 audit_sweep (A1-A5) + audit_basis_check (A6)
  3. 计算曲线 (CL/CD/Cm-α per V, 极曲线) 与覆盖矩阵 (V×α×β)
  4. 写 www/dashboard_data.json (仪表台唯一数据源)
  5. 写 out/audit_report.txt (人读报告)
蓝表未满 364 前不动 master aero_table.csv (验收通过才换)。
"""
import csv, json, os, statistics, subprocess, sys, time

HERE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
STATE = os.path.join(HERE, 'state')
WWW = os.path.join(HERE, 'www')
OUT = os.path.join(HERE, 'out')
AUDIT_DIR = os.path.join(ROOT, 'openfoam', 'airframe-sweep')
RED_TABLE = os.path.join(ROOT, 'guidance_sim', 'aero', 'aero_table_foldedfin_T0.csv')

QS = 'qianli@100.90.63.31'
VS = [15.0, 20.0, 25.0, 30.0]
ALPHAS = [-15, -12.5, -10, -7.5, -5, -2.5, 0, 2.5, 5, 7.5, 10, 12.5, 15]
BETAS = [-15, -10, -5, 0, 5, 10, 15]
TOTAL = len(VS) * len(ALPHAS) * len(BETAS)

def ssh_cat(remote, local, timeout=180):
    r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                        "ssh -o ConnectTimeout=15 %s 'cat %s 2>/dev/null'" % (QS, remote)],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode == 0 and r.stdout.strip():
        open(local, 'w', newline='').write(r.stdout)
        return True
    return False

def ssh_probe_int(remote, timeout=60):
    """远端整数探测 (pgrep 等); 远程命令禁用单引号 — 外层就是单引号包裹"""
    r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                        "ssh -o ConnectTimeout=15 %s '%s'" % (QS, remote)],
                       capture_output=True, text=True, timeout=timeout)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return -1

def load_table(path):
    rows = []
    try:
        lines = [ln for ln in open(path, encoding='utf-8', errors='replace') if not ln.startswith('#')]
    except FileNotFoundError:
        return rows
    for r in csv.DictReader(lines):
        try:
            rows.append({k: float(r[k]) for k in ('V', 'alpha', 'beta', 'CL', 'CD', 'Cm', 'CY', 'Cl', 'Cn')})
        except (KeyError, ValueError, TypeError):
            pass
    return rows

def parse_sweep_log(local_log):
    cur, prog = None, ''
    try:
        txt = open(local_log, encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        return cur, prog
    for ln in txt.splitlines():
        if ln.startswith('===== [') and '] V' in ln:
            cur = ln.split('] ', 1)[1].split(' =')[0].strip()
        elif 'meshing' in ln or 'solved' in ln or 'FAILED' in ln:
            prog = ln.strip()[:80]
    return cur, prog

def run_audit(script, table, extra=()):
    try:
        r = subprocess.run([sys.executable, os.path.join(AUDIT_DIR, script), table, *extra],
                           capture_output=True, text=True, timeout=300,
                           cwd=AUDIT_DIR)
        return (r.stdout or '') + (r.stderr or '')
    except Exception as e:
        return 'AUDIT ERR %s: %s' % (script, e)

def main():
    for d in (STATE, WWW, OUT):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    data = {'generated_ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'generated_epoch': time.time()}

    # -- 拉表 ---------------------------------------------------------------
    t0p = os.path.join(STATE, 't0_blue.csv')
    t1p = os.path.join(STATE, 't1_blue.csv')
    logp = os.path.join(STATE, 'sweep_t0v2.log')
    fcp = os.path.join(STATE, 'forces_r8b_parallel.csv')
    ok0 = ssh_cat('~/sweep_t0v2/t0_table.csv', t0p)
    okL = ssh_cat('~/sweep_t0v2/sweep.log', logp)
    ssh_cat('~/sweep_t1/t1_table.csv', t1p)
    ssh_cat('~/fluidx3d_v3/FluidX3D-master/bin/out/forces.csv', fcp)
    ssh_cat('~/fluidx3d_v3/FluidX3D-master/bin/out/forces_r8_folded.csv', os.path.join(STATE, 'forces_r8_folded.csv'))
    rows = load_table(t0p)
    red = load_table(RED_TABLE)
    data['sync'] = {'t0_ok': ok0, 'log_ok': okL, 'n_blue': len(rows), 'n_red': len(red)}

    # -- 进度 (ETA 滚动实测: 用 J1 自己的拉取历史斜率, 不再拍固定单耗) ----------
    cur, prog = parse_sweep_log(logp)
    done = len(rows)
    hist_p = os.path.join(STATE, 'pull_history.json')
    try:
        hist = json.load(open(hist_p))
    except Exception:
        hist = []
    hist = [h for h in hist if time.time() - h[0] < 6 * 3600]
    for i in range(1, len(hist)):
        if hist[i][0] - hist[i - 1][0] > 2 * 3600:  # 停机断点 (断电等), 丢弃更早历史防 ETA 被稀释
            hist = hist[i:]
            break
    if not hist or hist[-1][1] != done:
        hist.append([time.time(), done])
    json.dump(hist[-200:], open(hist_p, 'w'))
    eta_min, eta_src = None, 'pending'
    for h in hist:
        dt = hist[-1][0] - h[0]
        dd = done - h[1]
        if dt > 900 and dd > 0:  # 至少 15 分钟窗口且有推进
            eta_min = round((TOTAL - done) / (dd / dt) / 60)
            eta_src = 'rolling (%.2f case/min)' % (dd / dt / 60)
            break
    if eta_min is None and done:
        eta_min = round((TOTAL - done) * 15.0)
        eta_src = 'fixed 15min/case (复用档下限; 含建网格的姿态档实测约30min)'
    data['t0'] = {'done': done, 'total': TOTAL, 'current': cur, 'phase': prog,
                  'eta_min': eta_min, 'eta_src': eta_src, 'source': 'qianli sweep_t0v2'}
    seen = {(r['V'], r['alpha'], r['beta']) for r in rows}
    data['coverage'] = {str(int(v)): [[1 if (v, a, b) in seen else 0 for b in BETAS] for a in ALPHAS] for v in VS}
    t1rows = load_table(t1p)
    data['t1'] = {'done': len(t1rows), 'total': TOTAL, 'note': 'chain: T0-v2 完成后自动续'}
    lbm = ssh_probe_int('pgrep -cf "FluidX3[D]" || true')
    data['machines'] = {
        'qianli_cpu': {'role': 'T0-v2 蓝基准 L5/L7', 'status': 'solving' if okL else 'unknown',
                       'done': done, 'total': TOTAL},
        'qianli_gpu': {'role': 'T2 R8b LBM 平行基准',
                       'status': 'running' if lbm > 0 else 'paused (体素化玄学 T2 专项待查)'},
        'desktop': {'role': '审计/合并/交付 (只打杂)', 'status': 'idle'},
    }

    # -- T2 曲线 -------------------------------------------------------------
    t2 = []
    try:
        for ln in open(fcp):
            p = ln.strip().split(',')
            if len(p) == 7 and p[0] != 't':
                try: t2.append([float(p[0]), float(p[1]), float(p[2]), float(p[3])])
                except ValueError: pass
    except FileNotFoundError:
        pass
    dec = t2[::4]
    t2stat = None
    if len(t2) >= 20:
        tail = t2[-50:]
        t2stat = {'n': len(t2), 't_last': t2[-1][0],
                  'fy_mean': statistics.mean(c[2] for c in tail),
                  'fx_mean': statistics.mean(c[1] for c in tail)}
    data['t2'] = {'samples': dec, 'stats': t2stat, 'label': 'R8b 平行基准 α=12.5° (LBM lu)',
                  'live': lbm > 0}

    # -- 曲线 (蓝表 β=0, per V) ----------------------------------------------
    curves = {'alpha': ALPHAS, 'byV': {}}
    for v in VS:
        by_a = {}
        for r in rows:
            if r['V'] == v and r['beta'] == 0:
                by_a.setdefault(r['alpha'], []).append(r)
        if not by_a:
            continue
        xs = sorted(by_a)
        med = lambda k: [statistics.median(rr[k] for rr in by_a[x]) if x in by_a else None for x in ALPHAS]
        curves['byV'][str(int(v))] = {'CL': med('CL'), 'CD': med('CD'), 'Cm': med('Cm')}
    # CL_α 斜率 (V=25, |α|<=7.5, β=0)
    slope = None
    if 25.0 in curves['byV']:
        pts = [(a, c) for a, c in zip(ALPHAS, curves['byV']['25.0']['CL'])
               if c is not None and abs(a) <= 7.5]
        if len(pts) >= 3:
            n = len(pts); mx = sum(p[0] for p in pts)/n; my = sum(p[1] for p in pts)/n
            den = sum((p[0]-mx)**2 for p in pts)
            if den:
                slope = sum((p[0]-mx)*(p[1]-my) for p in pts)/den  # per deg
    # 极曲线
    polar = {}
    for v in VS:
        pts = [[r['CD'], r['CL']] for r in rows if r['V'] == v and r['beta'] == 0]
        if pts:
            polar[str(int(v))] = pts
    # 红基准对照 (β=0, V=25)
    red_cl = {}
    by_a = {}
    for r in red:
        if r['V'] == 25.0 and r['beta'] == 0:
            by_a.setdefault(r['alpha'], []).append(r['CL'])
    if by_a:
        red_cl = {'alpha': sorted(by_a), 'CL': [statistics.median(by_a[a]) for a in sorted(by_a)]}
    data['curves'] = {'cl_slope_per_deg': slope, 'cl_slope_per_rad': slope*57.2958 if slope else None,
                      'blue': curves, 'red_v25': red_cl, 'polar': polar}

    # -- 审计 ----------------------------------------------------------------
    audit_lines = []
    if rows:
        r1 = run_audit('audit_sweep.py', t0p, ['--report', os.path.join(OUT, 'audit_a1a5.txt')])
        r2 = run_audit('audit_basis_check.py', t0p, ['--compare', RED_TABLE])
        audit_lines = [ln for ln in (r1 + '\n' + r2).splitlines() if ln.strip()]
    else:
        audit_lines = ['蓝表为空, 审计跳过']
    def verdict(lines):
        if not lines: return 'SKIP'
        joined = '\n'.join(lines)
        if 'FAIL' in joined: return 'FAIL'
        if 'AUDIT ERR' in joined: return 'ERR'
        if 'WARN' in joined: return 'WARN'
        if 'PASS' in joined: return 'PASS'
        return 'SKIP'
    data['audit'] = {'a1a5': verdict(r1.splitlines()) if rows else 'SKIP',
                     'a6': verdict(r2.splitlines()) if rows else 'SKIP',
                     'a6_lines': [ln for ln in r2.splitlines() if ln.strip()][:8] if rows else []}

    # -- 写产物 --------------------------------------------------------------
    jp = os.path.join(WWW, 'dashboard_data.json')
    json.dump(data, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    rep = ['== J1 同步+审计报告 %s ==' % data['generated_ts'],
           '蓝表: %d/%d (拉取%s)' % (done, TOTAL, 'OK' if ok0 else 'FAIL'),
           '当前: %s %s' % (cur, prog),
           'ETA: %s [%s]' % ('%dh%02dm' % (eta_min//60, eta_min%60) if eta_min else '-', eta_src),
           'A1-A5: %s | A6: %s' % (data['audit']['a1a5'], data['audit']['a6']),
           *audit_lines[:20]]
    open(os.path.join(OUT, 'audit_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print('\n'.join(rep))
    print('dashboard_data.json ->', jp, '(%.1f KB, %.1fs)' % (os.path.getsize(jp)/1024, time.time()-t0))

if __name__ == '__main__':
    main()
