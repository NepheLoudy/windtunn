#!/usr/bin/env bash
# 11-11 chain 阈值 364→546 + 补跑/T1 网格改 V20-25 (546 目标口径; V15/30 已冷备)
# 安全序列: chain 在 sleep 循环里, kill 无风险; 改完立即重启回 wait 环
set -x
pkill -f 'chain_t1_v[3]'; sleep 1
pgrep -cf 'chain_t1_v[3]' && echo STILL_ALIVE || echo CHAIN_STOPPED
F=$HOME/chain_t1_v3.sh
cp "$F" "$F.bak_364_1111"
sed -i 's/if \[ "$n" -ge 364 \]; then break; fi/if [ "$n" -ge 546 ]; then break; fi/' "$F"
sed -i '27s/export SWEEP_V="15 20 25 30"/export SWEEP_V="20 21 22 23 24 25"/' "$F"
sed -i 's/engine relaunched for \$n\/364/engine relaunched for $n\/546/' "$F"
sed -i 's/rows=\$n < 364/rows=$n < 546/' "$F"
sed -i '50s/export SWEEP_V="15 20 25 30"/export SWEEP_V="20 21 22 23 24 25"/' "$F"
echo == 改后核对
grep -n '546\|SWEEP_V' "$F"
bash -n "$F" && echo SYNTAX_OK
# 重启 chain (guard 也兜底, 这里立即拉齐)
setsid nohup bash "$F" >> "$HOME/chain_v3.log" 2>&1 < /dev/null &
sleep 1
pgrep -cf 'chain_t1_v[3]' >/dev/null && echo CHAIN_RELAUNCHED || echo CHAIN_DEAD
