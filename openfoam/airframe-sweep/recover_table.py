#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表行回填 — results.json 已写而表行缺失的工况补投 (guard 引擎空闲时调用)

漏洞来源: run_sweep 每工况先写 results.json 再 append 表行, 断电/中断若卡在
两步之间, 行就丢了; 而 run_sweep_v2.sh 判重只看 results.json + 表判重集,
缺行的工况会被跳过且永不补投, chain 的补跑循环同样救不回 (results.json 在)。
收割机只清场数据、保留 results.json, 所以证据永在 — 本脚本按 coeffs 重投。

用法: python3 recover_table.py [sweep_root]   (默认 ~/sweep_t0v2)
重投方式与 run_sweep_v2.sh 完全一致: post_process.py --json <rj> --out <表>。
幂等: 已在表中的 (V,alpha,beta) 跳过。部署位置: qianli ~/recover_table.py
"""
import glob
import json
import os
import subprocess
import sys

PP = os.path.expanduser('~/windtunnel/openfoam/airframe-sweep/post_process.py')


def table_keys(tbl):
    have = set()
    if os.path.exists(tbl):
        for ln in open(tbl, encoding='utf-8', errors='replace'):
            if ln.startswith('#'):
                continue
            p = ln.strip().split(',')
            if len(p) >= 3:
                try:
                    have.add((round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4)))
                except ValueError:
                    pass
    return have


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/sweep_t0v2')
    tbl = os.path.join(root, 't0_table.csv')
    if not os.path.isdir(root):
        print('recover: no root %s' % root)
        return
    have = table_keys(tbl)
    fixed = missed = 0
    for rj in sorted(glob.glob(os.path.join(root, 'case_*', 'results.json'))):
        try:
            c = json.load(open(rj))['coeffs']
            key = (round(float(c['V']), 4), round(float(c['alpha']), 4), round(float(c['beta']), 4))
        except Exception as e:
            print('SKIP %s: %s' % (rj, e))
            continue
        if key in have:
            continue
        r = subprocess.run(['python3', PP, '--json', rj, '--out', tbl],
                           capture_output=True, text=True, timeout=120)
        tag = os.path.basename(os.path.dirname(rj))
        if r.returncode == 0:
            have.add(key)
            fixed += 1
            print('BACKFILL %s ok' % tag)
        else:
            missed += 1
            print('BACKFILL %s FAILED: %s' % (tag, (r.stderr or r.stdout)[-150:]))
    print('recover done: %d backfilled, %d failed' % (fixed, missed))


if __name__ == '__main__':
    main()
