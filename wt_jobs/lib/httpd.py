#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零依赖本地仪表台服务 — 禁缓存的静态文件服务器 (Ctrl+C 即停)

usage: py -3 lib/httpd.py [docroot] [port]
默认 docroot = ../www, 端口 8123。禁缓存头是修"浏览器看到空白"的根: 任何资源
永不 304, 数据 JSON 每次拉新。
"""
import http.server, os, socketserver, subprocess, sys, threading, time

# 自动拉新线程: 每 8 分钟后台跑一次 sync_and_audit (页面开着数据就永远新鲜, 不依赖手动 J1)
_sync_lock = threading.Lock()
def auto_sync():
    lib = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(lib, 'sync_and_audit.py')
    while True:
        time.sleep(480)
        if not _sync_lock.acquire(blocking=False):
            continue  # 上轮未完 (ssh 慢), 跳过本轮防叠加
        try:
            r = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=600)
            print('[auto-sync] %s' % ('ok' if r.returncode == 0 else 'FAIL ' + r.stderr[-200:]))
        except Exception as e:
            print('[auto-sync] err %s' % e)
        finally:
            _sync_lock.release()
        sys.stdout.flush()

threading.Thread(target=auto_sync, daemon=True).start()

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
docroot = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'www')
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8123
docroot = os.path.normpath(os.path.join(os.getcwd(), docroot)) if not os.path.isabs(docroot) else docroot
os.chdir(docroot)

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    def log_message(self, fmt, *args):
        sys.stdout.write('[%s] %s\n' % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('0.0.0.0', port), H) as srv:
    print('dashboard serving %s  ->  http://127.0.0.1:%d   (Ctrl+C 停止)' % (docroot, port))
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped.')
