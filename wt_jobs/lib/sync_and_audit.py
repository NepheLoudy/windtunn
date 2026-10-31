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

def ssh_out(remote, timeout=90):
    """远端多行文本拉取 (实时工况段); 禁用单引号"""
    r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                        "ssh -o ConnectTimeout=15 %s '%s'" % (QS, remote)],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout or ''

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

    # -- 实时工况 (live): 正在算什么/算到哪/收敛动态 (10-31 UI 迭代) -------------
    import re as _re
    sys.path.insert(0, AUDIT_DIR)
    try:
        from post_process import wind_axes as _wind_axes
    except Exception:
        _wind_axes = None
    live = {'phase': 'unknown'}
    try:
        raw = ssh_out(
            'C=$(ls -td ~/sweep_t0v2/case_* 2>/dev/null | head -1); '
            'echo "case=$(basename $C 2>/dev/null)"; '
            'pgrep -f snappyHexMes[h] >/dev/null && echo phase=meshing || '
            '{ pgrep -f foamRu[n] >/dev/null && echo phase=solving || '
            '{ pgrep -f run_sweep_v[2] >/dev/null && echo phase=pipeline || echo phase=idle; }; }; '
            'echo "chain=$(pgrep -cf chain_t1_v[3] || true)"; '
            'echo "reaper=$(pgrep -cf case_reape[r] || true)"; '
            'ping -c1 -W2 192.168.31.153 >/dev/null 2>&1 && echo nas=up || echo nas=down; '
            'echo "steps=$(grep -c "^Time =" "$C"/log.foamRun 2>/dev/null)"; '
            'grep "^endTime" "$C"/system/controlDict 2>/dev/null | head -1; '
            'echo ---LOG---; tail -c 60000 "$C"/log.foamRun 2>/dev/null; '
            'echo ---FORCES---; '
            'if [ -f "$C/postProcessing/forces/0/forces.dat" ]; then tail -n 400 "$C/postProcessing/forces/0/forces.dat"; '
            'else for f in "$C"/processor*/postProcessing/forces/0/forces.dat; do [ -f "$f" ] && tail -n 400 "$f"; done; fi; '
            'echo ---MACH---; uptime; df -h / | tail -1; '
            'echo ---TAIL---; tail -n 6 ~/sweep_t0v2/t0_table.csv 2>/dev/null', timeout=120)
        head = raw.split('---FORCES---')[0] if '---FORCES---' in raw else raw
        m = _re.search(r'^case=(.*)$', head, _re.M)
        if m: live['case'] = m.group(1).strip()
        m = _re.search(r'^phase=(.*)$', head, _re.M)
        if m: live['phase'] = m.group(1).strip()
        m = _re.search(r'^chain=(\d+)', head, _re.M)
        if m: live['chain'] = int(m.group(1))
        m = _re.search(r'^reaper=(\d+)', head, _re.M)
        if m: live['reaper'] = int(m.group(1))
        m = _re.search(r'^nas=(\w+)', head, _re.M)
        if m: live['nas'] = m.group(1)
        m = _re.search(r'^steps=(\d+)', head, _re.M)
        if m: live['steps'] = int(m.group(1))
        m = _re.search(r'^endTime\s+([\d.]+);?', head, _re.M)
        if m: live['endTime'] = float(m.group(1))
        m = _re.search(r'^Time\s*=\s*([\d.]+)', head.split('---LOG---')[-1], _re.M) if '---LOG---' in head else None
        if m: live['last_time'] = float(m.group(1))
        # 残差序列 (Ux / p): 求解日志尾部
        log_tail = head.split('---LOG---')[-1] if '---LOG---' in head else ''
        res = _re.findall(r'Solving for (\w+), Initial residual = ([\d.eE++-]+)', log_tail)
        seq = {'Ux': [], 'p': []}
        for var, val in res:
            if var in seq and len(seq[var]) < 400:
                seq[var].append(float(val))
        live['residuals'] = seq
        # 并行 forces 聚合 (14 processor 同 t 求和) → 实时 CL/CD
        fsec = raw.split('---FORCES---')[1].split('---MACH---')[0] if '---FORCES---' in raw else ''
        acc = {}
        _tri = _re.compile(r'\(([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\)')
        for ln in fsec.splitlines():
            tri = _tri.findall(ln)
            if len(tri) not in (2, 4, 6):
                continue
            try:
                t = float(ln.split()[0])
            except (ValueError, IndexError):
                continue
            # 2 三元组 = case 级 master 聚合 (F, M); 4/6 = processor 分片 (p+v) — 求和口径同 post_process
            if len(tri) == 2:
                F = [float(tri[0][j]) for j in range(3)]
            else:
                h2 = len(tri) // 2
                F = [sum(float(tri[i][j]) for i in range(h2)) for j in range(3)]
            a = acc.setdefault(round(t, 3), [0.0, 0.0, 0.0])
            for j in range(3):
                a[j] += F[j]
        if acc and _wind_axes and live.get('case'):
            mc = _re.search(r'V([\d.]+)_a(-?[\d.]+)_b(-?[\d.]+)', live['case'])
            if mc:
                V, al, be = float(mc.group(1)), float(mc.group(2)), float(mc.group(3))
                S_REF = 0.010306121
                try:
                    for ln in open(os.path.join(STATE, 't0_blue.csv'), encoding='utf-8', errors='replace'):
                        if ln.startswith('#') and 'S_REF' in ln:
                            S_REF = float(_re.search(r'S_REF=([\d.eE+.-]+)', ln).group(1))
                            break
                except Exception:
                    pass
                qS = 0.5 * 1.225 * V * V * S_REF
                drag, lift, side = _wind_axes(al, be)
                ser = []
                for t in sorted(acc)[-400:]:
                    F = acc[t]
                    ser.append([t, sum(f * x for f, x in zip(F, lift)) / qS,
                                sum(f * x for f, x in zip(F, drag)) / qS])
                live['forces'] = ser
        mach = raw.split('---MACH---')[1].split('---TAIL---')[0] if '---MACH---' in raw else ''
        mm = _re.search(r'load average: ([\d.]+), ([\d.]+), ([\d.]+)', mach)
        if mm: live['load'] = [float(mm.group(1)), float(mm.group(2)), float(mm.group(3))]
        md = _re.search(r'(\S+)\s+\S+\s+\S+\s+\S+\s+(\S+)\s+\S+$', mach.strip().splitlines()[-1] if mach.strip() else '')
        if md: live['disk_avail'] = md.group(2)
        tt = raw.split('---TAIL---')[1] if '---TAIL---' in raw else ''
        live['table_tail'] = [ln.strip() for ln in tt.splitlines()
                              if ln.strip() and not ln.startswith('V,alpha') and not ln.startswith('#')][-5:]
    except Exception as e:
        live['err'] = (live.get('err') or '') + str(e)[:100]
    data['live'] = live

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
