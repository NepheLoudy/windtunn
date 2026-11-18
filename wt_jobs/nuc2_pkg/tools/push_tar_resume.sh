#!/bin/bash
# 分块续传 tar 到 NUC#1 (从远端已有 offset 继续, 每块 512MB)
set -e
SRC=/mnt/d/nuc_ubuntu_baseline.tar
REMOTE=lenovo@192.168.137.28
BCHUNK=$((512*1024*1024))
TOTAL=11409049600

have=$(ssh -o ConnectTimeout=10 $REMOTE 'cmd /c for %F in (D:\nuc_ubuntu_baseline.tar) do @echo %~zF' 2>/dev/null | tr -d '\r\n ')
have=${have:-0}
echo "remote has: $have / $TOTAL"
if [ "$have" -ge "$TOTAL" ]; then echo "ALREADY COMPLETE"; exit 0; fi

ssh $REMOTE 'if not exist D:\nuc_parts mkdir D:\nuc_parts' 2>/dev/null

start=0
part=0
while [ $start -lt $TOTAL ]; do
  end=$((start + BCHUNK))
  [ $end -gt $TOTAL ] && end=$TOTAL
  len=$((end - start))
  p4=$(printf "%04d" $part)
  echo "part $p4: offset=$start len=$len"
  dd if=$SRC bs=1M skip=$((start/1024/1024)) count=$(((len + 1048575)/1048576)) 2>/dev/null |
    ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=6 $REMOTE "cmd /c more > D:\nuc_parts\p_$p4"
  rsz=$(ssh $REMOTE "cmd /c for %F in (D:\nuc_parts\p_$p4) do @echo %~zF" 2>/dev/null | tr -d '\r\n ')
  echo "  remote part size: ${rsz:-?} (expect ~$len)"
  if [ -z "$rsz" ] || [ "$rsz" -lt $((len - 2097152)) ]; then
    echo "  retry once"
    dd if=$SRC bs=1M skip=$((start/1024/1024)) count=$(((len + 1048575)/1048576)) 2>/dev/null |
      ssh -o ServerAliveInterval=15 $REMOTE "cmd /c more > D:\nuc_parts\p_$p4"
    rsz=$(ssh $REMOTE "cmd /c for %F in (D:\nuc_parts\p_$p4) do @echo %~zF" 2>/dev/null | tr -d '\r\n ')
    if [ -z "$rsz" ] || [ "$rsz" -lt $((len - 2097152)) ]; then echo "FAILED twice - abort at part $p4"; exit 1; fi
  fi
  start=$end
  part=$((part+1))
done

echo '=== merging on remote ==='
ssh $REMOTE 'cmd /c del D:\nuc_ubuntu_final.tar 2>nul & cmd /c copy /b D:\nuc_parts\p_* D:\nuc_ubuntu_final.tar'
final=$(ssh $REMOTE 'cmd /c for %F in (D:\nuc_ubuntu_final.tar) do @echo %~zF' 2>/dev/null | tr -d '\r\n ')
echo "final merged: $final / expect $TOTAL"
if [ "$final" = "$TOTAL" ]; then echo MERGE_OK; else echo SIZE_MISMATCH; exit 1; fi
