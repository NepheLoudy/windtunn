#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零依赖本地仪表台服务 — 禁缓存的静态文件服务器 (Ctrl+C 即停)

usage: py -3 lib/httpd.py [docroot] [port]
默认 docroot = ../www, 端口 8123。禁缓存头是修"浏览器看到空白"的根: 任何资源
永不 304, 数据 JSON 每次拉新。
"""
import http.server, json, os, socketserver, subprocess, sys, time

# 11-02: auto-sync 线程已移除 — 同步外置为 schtasks WT_sync (每 2min 跑 j1, 幂等自动退出)。
# httpd 内部线程曾静默死亡致数据 30h 不更新; 外置任务+guard 模式才是可靠架构。

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

    # ---- 质量属性 UI API (曼波 11-01: 3D 里选中轴线+定重心+填重量) ------------
    # 意图层落盘 state/mass_props_ui.json — 不动正本 mass_properties.json:
    # T0-v2c 在跑, post_process 每工况读正本, 中途换参考点=前后行 M_B 不一致;
    # 蓝表出全后随合并步骤统一应用 + recompute_cm 以新 com 重算全表力矩。
    def _mass_paths(self):
        root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
        canon = os.path.join(root, 'openfoam', 'airframe-sweep', 'cad', 'v1', 'cfd', 'mass_properties.json')
        ui = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'state', 'mass_props_ui.json')
        return canon, os.path.normpath(ui)

    def _mass_state(self):
        canon, ui = self._mass_paths()
        st = {}
        try:
            st = json.load(open(canon, encoding='utf-8'))
        except Exception:
            pass
        cur = {'mass_g': round(float(st.get('mass_kg', 0.16)) * 1000, 1),
               'com_x_mm': round(float(st.get('com_B', [0, 0, 0])[0]) * 1000, 2),
               'com_y_mm': round(float(st.get('com_B', [0, 0, 0])[1]) * 1000, 2),
               'com_z_mm': round(float(st.get('com_B', [0, 0, 0])[2]) * 1000, 2),
               'status': st.get('_status', ''), 'updated': None}
        try:
            ui_st = json.load(open(ui, encoding='utf-8'))
            cur.update(ui_st)
        except Exception:
            pass
        return cur

    def do_GET(self):
        if self.path.startswith('/api/mass_props'):
            body = json.dumps(self._mass_state()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/api/mass_props'):
            self.send_error(404)
            return
        try:
            ln = int(self.headers.get('Content-Length', 0))
            req = json.loads(self.rfile.read(ln))
            mass_g = float(req['mass_g'])
            com_x_mm = float(req['com_x_mm'])
            if not (10 <= mass_g <= 2000):
                raise ValueError('mass_g 越界 (10-2000)')
            if not (-200 <= com_x_mm <= 200):
                raise ValueError('com_x_mm 越界 (±200)')
        except Exception as e:
            body = json.dumps({'ok': False, 'err': str(e)}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        import json as _json
        _, ui = self._mass_paths()
        os.makedirs(os.path.dirname(ui), exist_ok=True)
        st = {'mass_g': mass_g, 'com_x_mm': com_x_mm,
              'updated': time.strftime('%Y-%m-%d %H:%M:%S'),
              'note': 'UI 交互定值 (3D 轴线选重心) — 蓝表出全后随合并应用正本+qianli, recompute_cm 以此重算全表力矩'}
        with open(ui, 'w', encoding='utf-8') as f:
            _json.dump(st, f, ensure_ascii=False, indent=1)
        body = json.dumps({'ok': True, 'saved': st}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        sys.stdout.write('[mass_props] saved mass=%.1fg com_x=%.2fmm\n' % (mass_g, com_x_mm))
        sys.stdout.flush()

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('0.0.0.0', port), H) as srv:
    print('dashboard serving %s  ->  http://127.0.0.1:%d   (Ctrl+C 停止)' % (docroot, port))
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped.')
