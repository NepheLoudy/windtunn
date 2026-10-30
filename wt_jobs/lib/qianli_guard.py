#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J4: qianli 哨兵 — schtasks 每 30min 触发一次, 幂等无常驻

qianli 断电重启后什么都不会自动拉起 (三个守护都是 setsid nohup 手工挂的),
本机是 24h 节点, 由它隔 30min 探一次活、把掉线的守护拉回来。动作全部走
安全路径, 只有一条铁律:

  永不调用 launch_t0v2b.sh — 那是 rm -rf 全清启动器, 中途调用会删光
  已完成工况。断点续传在 run_sweep_v2.sh 的判重层, 引擎补拉由 chain v3
  的补跑循环负责 (它直接拉 run_sweep_v2.sh), guard 只负责把 chain 拉活。

修复矩阵:
  chain 缺失            → 重拉 chain_t1_v3.sh (T0/T1 两阶段通用: 它自会
                          等引擎/补跑/放行 T1 并为 T1 拉收割机)
  reaper(T0) 缺失且 T1 未开始 → 重拉 case_reaper.sh sweep_t0v2 600
  reaper(T1) 缺失且 T1 已开始 → 重拉 case_reaper.sh sweep_t1 600
  引擎空闲              → 跑 recover_table.py 回填缺行 (results.json 在
                          而表行缺的工况; 引擎跑动时不跑防双投竞态)
  NAS                   → 只探活记日志 (回归后 reaper 表推送自动恢复)

日志: wt_jobs/out/qianli_guard.log (单行摘要 + 动作明细, >1MB 轮转)
退出码: 0=无需动作 1=有动作 2=ssh 失败 3=探活异常

探活协议注意: PROBE 里禁用单引号 (ssh 包装层就是单引号, 会碎), 模式串一律
双引号 + 字符类断自匹配 (chain_t1_v[3] 教训); pgrep 只回 0/1 不回计数。
"""
import os
import subprocess
import sys
import time

HERE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(HERE, 'out')
LOG = os.path.join(OUT, 'qianli_guard.log')
QS = 'qianli@100.90.63.31'
TOTAL = 364

PROBE = r"""
pgrep -cf "chain_t1_v[3]" >/dev/null && echo "chain=1" || echo "chain=0"
pgrep -cf "run_sweep_v[2]" >/dev/null && echo "eng_sweep=1" || echo "eng_sweep=0"
pgrep -cf "foamRu[n]" >/dev/null && echo "eng_foam=1" || echo "eng_foam=0"
pgrep -cf "snappyHexMes[h]" >/dev/null && echo "eng_snap=1" || echo "eng_snap=0"
pgrep -af "case_reape[r].sh" | grep -q sweep_t0v2 && echo "reaper_t0=1" || echo "reaper_t0=0"
pgrep -af "case_reape[r].sh" | grep -q "sweep_t1 " && echo "reaper_t1=1" || echo "reaper_t1=0"
[ -f "$HOME/sweep_t0v2/t0_table.csv" ] && echo "rows=$(( $(wc -l < "$HOME/sweep_t0v2/t0_table.csv") - 2 ))" || echo "rows=0"
[ -f "$HOME/sweep_t1/sweep.log" ] && echo "t1=started" || echo "t1=no"
ping -c1 -W2 192.168.31.153 >/dev/null 2>&1 && echo "nas=up" || echo "nas=down"
"""


def ssh_run(cmd, timeout=90):
    r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                        "ssh -o ConnectTimeout=15 %s %s" % (QS, "'%s'" % cmd)],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or ''), (r.stderr or '')


def probe():
    rc, out, err = ssh_run(PROBE)
    if rc != 0:
        return None, 'ssh rc=%d %s' % (rc, err.strip()[-120:])
    st = {}
    for ln in out.splitlines():
        if '=' in ln:
            k, _, v = ln.partition('=')
            st[k.strip()] = v.strip()
    need = {'chain', 'eng_sweep', 'eng_foam', 'eng_snap', 'reaper_t0',
            'reaper_t1', 'rows', 't1', 'nas'}
    if not need.issubset(st):
        return None, 'probe incomplete: %s' % sorted(st)
    return st, ''


def relaunch(remote_cmd, what):
    rc, out, err = ssh_run(remote_cmd, timeout=30)
    return 'RELAUNCH %s rc=%d %s' % (what, rc, (out or err).strip()[-80:])


def recover(root, label):
    rc, out, err = ssh_run('python3 "$HOME/recover_table.py" "$HOME/%s"' % root, timeout=300)
    bf = [ln for ln in out.splitlines() if 'BACKFILL' in ln or 'recover done' in ln]
    if bf or rc != 0:
        return 'RECOVER %s rc=%d: %s' % (label, rc, ' | '.join(bf[-3:]) or err.strip()[-120:])
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    st, err = probe()
    lines = ['[%s] %s' % (ts, err if err else ' '.join('%s=%s' % kv for kv in sorted(st.items())))]
    code = 0
    if st is None:
        lines.append('  -> probe failed, no action (断网/重启中? 下轮再试)')
        code = 2 if 'ssh rc' in err else 3
    else:
        engine = st['eng_sweep'] == '1' or st['eng_foam'] == '1' or st['eng_snap'] == '1'
        t1_started = st['t1'] == 'started'
        try:
            rows = int(st['rows'])
        except ValueError:
            rows = 0
        actions = []
        if st['chain'] == '0':
            actions.append(relaunch(
                'setsid nohup bash "$HOME/chain_t1_v3.sh" >> "$HOME/chain_v3.log" 2>&1 < /dev/null & '
                'sleep 1; pgrep -cf "chain_t1_v[3]" >/dev/null && echo alive || echo dead', 'chain'))
        if not t1_started and st['reaper_t0'] == '0':
            actions.append(relaunch(
                'setsid nohup bash "$HOME/case_reaper.sh" "$HOME/sweep_t0v2" 600 '
                '>> "$HOME/reaper.log" 2>&1 < /dev/null & sleep 1', 'reaper_t0'))
        if t1_started and st['reaper_t1'] == '0':
            actions.append(relaunch(
                'setsid nohup bash "$HOME/case_reaper.sh" "$HOME/sweep_t1" 600 '
                '>> "$HOME/sweep_t1/reaper.log" 2>&1 < /dev/null & sleep 1', 'reaper_t1'))
        if not engine:
            for root, label in (('sweep_t0v2', 't0'), ('sweep_t1', 't1')):
                if root == 'sweep_t1' and not t1_started:
                    continue
                a = recover(root, label)
                if a:
                    actions.append(a)
        if actions:
            code = 1
            lines.extend('  -> ' + a for a in actions)
        if rows and rows < TOTAL and not engine:
            lines.append('  -> note: engine idle at %d/%d, chain owns relaunch (chain 已拉活或其补跑循环 10min 内接手)' % (rows, TOTAL))
    log(lines)
    print('\n'.join(lines))
    sys.exit(code)


def log(lines):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1024 * 1024:
            os.replace(LOG, LOG + '.old')
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass


if __name__ == '__main__':
    main()
