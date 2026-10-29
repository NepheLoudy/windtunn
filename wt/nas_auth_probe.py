#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧 NAS (192.168.31.153:2222) 凭据矩阵试探 — 曼波授权: cquqianli2026 及其变式
成功即打印用户名+探明 NAS 侧存储路径, 写 nas_creds.txt (本地, gitignore)。"""
import socket, sys, time
import paramiko

HOST, PORT = '192.168.31.153', 2222
USERS = ['qianli', 'root', 'admin', 'cquqianli', 'manbo']
PWS = ['cquqianli2026', 'Cquqianli2026', 'cquqianli2026!', 'cquqianli2026@',
       'cquqianli2026#', 'CQUQIANLI2026', 'cquqianli.2026', 'cquqianli2026!@#']

ok = None
for u in USERS:
    for pw in PWS:
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=u, password=pw, timeout=8,
                      allow_agent=False, look_for_keys=False)
            ok = (u, pw, c)
            print('AUTH-OK: %s / %s' % (u, pw))
            break
        except paramiko.AuthenticationException:
            print('fail: %-10s %s' % (u, pw[:6] + '***'))
            time.sleep(0.2)
        except Exception as e:
            print('conn-err: %s' % str(e)[:80])
            time.sleep(1)
    if ok:
        break

if not ok:
    print('ALL-FAILED — 矩阵穷尽, 需要曼波给准确凭据')
    sys.exit(1)

u, pw, c = ok
def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=15)
    return o.read().decode(errors='replace').strip(), e.read().decode(errors='replace').strip()

print('--- NAS 侧侦察 ---')
for cmd in ('uname -a', 'df -h | tail -5', 'ls /', 'ls /volume1 /mnt /share 2>/dev/null | head'):
    o, _ = run(cmd)
    print('$ %s\n%s' % (cmd, o[:400]))

open('nas_creds.txt', 'w').write('host=%s\nport=%d\nuser=%s\npass=%s\n' % (HOST, PORT, u, pw))
print('creds -> nas_creds.txt (本地)')
c.close()
