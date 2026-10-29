#!/usr/bin/env bash
# nas_push — 计算平台(qianli) → NAS vault 事件式推送 (曼波 10-30 定: 交换只发生在
# 计算平台工作时/调用需求时, 平时不动; 本机退出数据链路)
# 用法: nas_push <本地路径> [vault 相对路径]   (相对路径缺省=文件名归类到 incoming/)
# 语义: rsync 推送 + 双端核数(文件数/字节) + 通过即打标记; 失败留本地不删(推过的可重推增量)
set -u
NAS="qianli@192.168.31.153"
SSH="ssh -p 2222"
VAULT="/mnt/nas_data/公用/windtunnel-vault"
LOG="$HOME/nas_push.log"
SRC=${1:?usage: nas_push <path> [vault_rel]}
REL=${2:-incoming/$(basename "$SRC")}
[ -e "$SRC" ] || { echo "no such path: $SRC" | tee -a "$LOG"; exit 1; }

if [ -d "$SRC" ]; then
  n_src=$(find "$SRC" -type f | wc -l)
  b_src=$(find "$SRC" -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}')
  $SSH "$NAS" "mkdir -p '$VAULT/$REL'"
  rsync -a --partial -e "$SSH" "$SRC/" "$NAS:$VAULT/$REL/" || { echo "RSYNC-FAIL $REL $(date)" >> "$LOG"; exit 1; }
  remote=$($SSH "$NAS" "cd '$VAULT/$REL' && find . -type f | wc -l && find . -type f -printf '%s\n' | awk '{s+=\$1} END{print s+0}'")
  n_r=$(echo "$remote" | sed -n 1p); b_r=$(echo "$remote" | sed -n 2p)
  if [ "$n_src" = "$n_r" ] && [ "$b_src" = "$b_r" ]; then
    echo "PUSH-VERIFIED $REL: $n_r files $b_r bytes $(date)" >> "$LOG"; echo "verified -> $REL"
  else
    echo "MISMATCH $REL: src $n_src/$b_src vs nas $n_r/$b_r $(date)" >> "$LOG"; exit 1
  fi
else
  sz=$(stat -c%s "$SRC")
  $SSH "$NAS" "mkdir -p '$VAULT/$(dirname "$REL")'"
  rsync -a --partial -e "$SSH" "$SRC" "$NAS:$VAULT/$REL" || { echo "RSYNC-FAIL $REL $(date)" >> "$LOG"; exit 1; }
  b_r=$($SSH "$NAS" "stat -c%s '$VAULT/$REL'")
  if [ "$sz" = "$b_r" ]; then
    echo "PUSH-VERIFIED $REL: 1 file $b_r bytes $(date)" >> "$LOG"; echo "verified -> $REL"
  else
    echo "MISMATCH $REL: src $sz vs nas $b_r $(date)" >> "$LOG"; exit 1
  fi
fi
