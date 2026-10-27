#!/usr/bin/env bash
# 算力节点仪表台部署: 数据循环 + HTTP 服务 (Tailscale 网内浏览器直接访问)
#   usage: deploy_dashboard.sh [port]
#   访问: http://<节点 tailscale IP>:<port>/dashboard.html
set -u
PORT=${1:-8080}
DASH=$HOME/dashboard
pkill -f "http.server $PORT" 2>/dev/null
sleep 1
mkdir -p "$DASH"

# 数据循环: 每 20s 刷新 progress.json (节点本地) + t1_table.csv 快照
cat > "$HOME/dashboard_update.sh" <<'EOF'
#!/usr/bin/env bash
DASH=$HOME/dashboard
ROOT=$HOME/sweep_t1
while true; do
  DONE=$(grep -c '"coeffs"' "$ROOT"/*/results.json 2>/dev/null | grep -c ':1$')
  CUR=$(grep -o '===== \[[0-9]*\] [^ ]*' "$ROOT/sweep.log" 2>/dev/null | tail -1 | awk '{print $3}')
  RUN_MIN=$(( ( $(date +%s) - $(stat -c %Y "$ROOT/sweep.log" 2>/dev/null || date +%s) ) / 60 ))
  DONE_FLAG=0
  grep -q "扫气完成" "$ROOT/sweep.log" 2>/dev/null && DONE_FLAG=1
  printf '{"batch":"T1 高保真扫气","done":%s,"total":364,"current":"%s","step":"solve","run_min":%s,"eta_min":-1,"done_flag":%s}\n' \
    "${DONE:-0}" "${CUR:-?}" "$RUN_MIN" "$DONE_FLAG" > "$DASH/progress.json"
  cp "$ROOT/t1_table.csv" "$DASH/t1_table.csv" 2>/dev/null
  sleep 20
done
EOF
chmod +x "$HOME/dashboard_update.sh"

# 杀旧循环, 起新循环 (独立会话)
for p in $(pgrep -f dashboard_update.sh); do kill -9 $p 2>/dev/null; done
setsid nohup "$HOME/dashboard_update.sh" > /dev/null 2>&1 < /dev/null &

# HTTP 服务 (Tailscale IP + localhost)
setsid nohup python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$DASH" > /dev/null 2>&1 < /dev/null &
sleep 2
TSIP=$(/usr/bin/tailscale ip -4 2>/dev/null | head -1)
echo "仪表台已部署:"
echo "  本机访问: http://$TSIP:$PORT/dashboard.html"
echo "  数据刷新: 每 20s (progress + 系数表)"
