#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_master — 多扫气表合并 → master aero_table.csv (E2, 2026-11-03)

为什么存在: T0 蓝表(sweep_t0v2) / T1 高保真表(sweep_t1) 分机分目录生产,
交付正本是 guidance_sim/aero/aero_table.csv 单文件 — 合并时必须:
  ①表头元数据重建: S_REF/L_REF/RHO/MOMENT_REF 逐输入一致性核对 (不一致即拒合,
    防 10-31 口径类事故混档)
  ②七键判重 (V,α,β,de,da,dr): 重复键按来源优先级取档, 重复=事故信号要报告
  ③来源分档列 source: t0/t1 网格档可追溯, 力矩类以 T1 为可信档 (fidelity_1101)
  ④MOMENT_REF 逐行核对: 行内 moment_ref 与表头不符的行打 FLAG (recompute_cm 链)

用法:
  python3 merge_master.py --inputs "host:path..." [--out aero_table.csv] [--dry-run]
  python3 merge_master.py --local ~/sweep_t0v2/t0_table.csv --local ~/sweep_t1/t1_table.csv
  (qianli 表先经 wt_jobs J1 同步到本地 state/, 或 WSL ssh cat — 见 --pull)

不自动覆盖正本: 输出默认 ./aero_table.master.csv, 人工核对后手动替换正本。
依赖: 仅标准库。
"""
import argparse
import csv
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER_HEADER_KEYS = ('S_REF', 'L_REF', 'RHO', 'MOMENT_REF')
KEYCOLS = ('V', 'alpha', 'beta', 'de', 'da', 'dr')
VALCOLS = ('CL', 'CD', 'Cm', 'CY', 'Cl', 'Cn')


def parse_meta(lines):
    """'# K=V' 行 → dict; 非 '#' 行原样返回"""
    meta, body = {}, []
    for ln in lines:
        s = ln.strip()
        if s.startswith('#') and '=' in s:
            for tok in s.lstrip('#').split():
                if '=' in tok:
                    k, _, v = tok.partition('=')
                    if k in MASTER_HEADER_KEYS:
                        meta[k] = v
        elif s:
            body.append(ln)
    return meta, body


def read_table(path, source):
    """本地表文件 → (meta, rows)；rows 每行带 source 列"""
    meta, body = parse_meta(open(path, encoding='utf-8', errors='replace').readlines())
    rows = []
    rdr = csv.DictReader(ln for ln in body if not ln.startswith('#'))
    for r in rdr:
        try:
            row = {k: float(r[k]) for k in KEYCOLS + VALCOLS}
        except (KeyError, ValueError, TypeError):
            continue  # 半截行 (断电窗口) 跳过并计数
        row['source'] = source
        row['_file'] = os.path.basename(path)
        rows.append(row)
    return meta, rows


def pull_remote(host_remote_pairs, tmpdir):
    """经 WSL ssh 把 qianli 表拉到本地 tmpdir, 返回本地路径列表"""
    out = []
    for i, (host, remote) in enumerate(host_remote_pairs):
        local = os.path.join(tmpdir, 'pull_%d.csv' % i)
        r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                            "ssh -o ConnectTimeout=15 %s 'cat %s 2>/dev/null'" % (host, remote)],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            open(local, 'w', newline='').write(r.stdout)
            out.append(local)
    return out


def split_spec(spec):
    """'PATH[:SOURCE]' → (path, source)。PATH 是 Windows 盘符路径 (D:/...) 时
    冒号拆分必须跳过第 2 个字符的盘符冒号。"""
    if len(spec) > 2 and spec[1] == ':' and spec[0].isalpha():
        rest = spec[2:]
        path, _, src = rest.partition(':')
        return spec[0] + ':' + path, src
    path, _, src = spec.partition(':')
    return path, src


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--local', action='append', default=[], metavar='PATH[:SOURCE]',
                    help='本地表 (可多次); 默认 source=文件名去后缀')
    ap.add_argument('--pull', action='append', default=[], metavar='HOST:REMOTE[:SOURCE]',
                    help='远端表经 ssh 拉取合并 (可多次)')
    ap.add_argument('--out', default='aero_table.master.csv')
    ap.add_argument('--dry-run', action='store_true', help='只报告不落盘')
    ap.add_argument('--prefer', default='t1,t0', help='重复键来源优先级 (逗号分隔, 前者优先)')
    args = ap.parse_args()

    tables = []  # (source, meta, rows)
    for spec in args.local:
        path, src = split_spec(spec)
        source = src or os.path.splitext(os.path.basename(path))[0]
        if not os.path.exists(path):
            print('WARN 本地表不存在, 跳过: %s' % path)
            continue
        meta, rows = read_table(path, source)
        tables.append((source, meta, rows, path))

    if args.pull:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pairs = []
            for spec in args.pull:
                host, _, rest = spec.partition(':')
                remote, _, src = rest.partition(':')
                pairs.append((host, remote, src))
            pulled = pull_remote([(h, r) for h, r, _ in pairs], td)
            for (h, r, src), path in zip(pairs, pulled):
                source = src or ('%s:%s' % (h.split('@')[0], os.path.basename(r)))
                meta, rows = read_table(path, source)
                tables.append((source, meta, rows, path))

    if not tables:
        print('ERR 无可合并输入'); return 2

    # ---- ① 表头元数据一致性 ----
    print('== 输入表头一致性 ==')
    base = None
    consistent = True
    for source, meta, rows, path in tables:
        miss = [k for k in MASTER_HEADER_KEYS if k not in meta]
        print('  %-24s %5d 行  %s%s' % (source, len(rows),
              ' '.join('%s=%s' % (k, meta.get(k, '?')) for k in MASTER_HEADER_KEYS),
              ('  ⚠ 缺 %s' % miss) if miss else ''))
        if miss:
            consistent = False
        if base is None:
            base = meta
        elif meta != base:
            diff = {k: (base.get(k), meta.get(k)) for k in MASTER_HEADER_KEYS
                    if meta.get(k) != base.get(k)}
            print('  🔴 元数据不一致 %s: %s' % (source, diff))
            consistent = False
    if not consistent:
        print('ERR 表头不一致 — 拒合 (口径事故防线); 单表可先各自出档')
        # 不硬退出: 退出码标记, 仍可 --dry-run 查看
        if not args.dry_run:
            return 3

    # ---- ② 七键判重合并 ----
    prefer = [s.strip() for s in args.prefer.split(',')]
    rank = {s: i for i, s in enumerate(prefer)}
    merged, dups, flags = {}, [], []
    for source, meta, rows, path in tables:
        for row in rows:
            key = tuple(round(row[k], 6) for k in KEYCOLS)
            if key in merged:
                old = merged[key]
                dups.append((key, old['source'], source))
                if rank.get(source, 99) < rank.get(old['source'], 99):
                    merged[key] = row
            else:
                merged[key] = row

    # ---- ③④ 输出 ----
    out_rows = sorted(merged.values(), key=lambda r: (r['V'], r['alpha'], r['beta'], r['de'], r['da'], r['dr']))
    hdr = '# ' + ' '.join('%s=%s' % (k, base[k]) for k in MASTER_HEADER_KEYS)
    # source 分档走注释行 (lookup_aero.from_csv 严格校验表头=KEYS+COEFFS,
    # 数据列多一个 source 都会拒表 — 2026-11-03 E4 集成测试抓到)
    src_map = {}
    for r in out_rows:
        src_map.setdefault(r['source'], []).append(
            '%g,%g,%g,%g,%g,%g' % tuple(r[k] for k in KEYCOLS))
    src_lines = ['# SOURCE %s n=%d' % (s, len(v)) for s, v in src_map.items()]
    if not args.dry_run:
        with open(args.out, 'w', newline='', encoding='utf-8') as f:
            f.write(hdr + '\n')
            for sl in src_lines:
                f.write(sl + '\n')
            w = csv.writer(f)
            w.writerow(list(KEYCOLS) + list(VALCOLS))
            for r in out_rows:
                w.writerow([r[k] for k in KEYCOLS] + [r[k] for k in VALCOLS])
        print('== 写出 %s: %d 行 (表头 %s) ==' % (args.out, len(out_rows), hdr))
        print('   %s' % ' | '.join(src_lines))
    else:
        print('== DRY-RUN: 将写 %d 行, 表头 %s ==' % (len(out_rows), hdr))

    if dups:
        print('🔴 重复键 %d 条 (按优先级 %s 取档):' % (len(dups), ','.join(prefer)))
        for key, a, b in dups[:10]:
            print('   V=%g α=%g β=%g δ=(%g,%g,%g): %s ← %s' % (*key, a, b))
        if len(dups) > 10:
            print('   ... 共 %d' % len(dups))
    else:
        print('✅ 零重复键')
    print('来源分布: %s' % ', '.join('%s=%d' % (s, sum(1 for r in out_rows if r['source'] == s))
                                      for s in dict.fromkeys(r['source'] for r in out_rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
