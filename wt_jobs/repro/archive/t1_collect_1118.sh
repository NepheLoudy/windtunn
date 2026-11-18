#!/usr/bin/env bash
# t1_collect_1118.sh — T1 审计只读数据采集 (不碰任何进程/文件内容不修改)
cd "$HOME/sweep_t1" || exit 1
OUT="$HOME/t1_collect_1118.txt"
{
echo '### casedirs: name|mtime_epoch'
find . -maxdepth 1 -type d -name 'case_*' -printf '%f|%T@\n' | sort
echo '### logfiles: path|mtime_epoch|size'
find . -maxdepth 2 -name 'log.*' -printf '%p|%T@|%s\n' | sort
echo '### logtimes: path|header|last_exec'
for p in case_*/log.blockMesh case_*/log.snappy case_*/log.foamRun; do
  [ -f "$p" ] || continue
  hdr=$(awk 'NR<=40 && ($0 ~ /^[[:space:]]*(Date|date)[[:space:]]*:/ || $0 ~ /^[[:space:]]*(Time|time)[[:space:]]*:/){gsub(/[[:space:]]+/," "); a=a $0 " "} END{print a}' "$p")
  ex=$(grep -a 'ExecutionTime' "$p" | tail -1 | tr -s ' \t' ' ')
  printf '%s|%s|%s\n' "$p" "$hdr" "$ex"
done
echo '### errsig: path|signature'
for p in case_*/log.blockMesh case_*/log.snappy; do
  [ -f "$p" ] || continue
  sig=$(grep -am1 -iE 'FOAM FATAL|未找到命令|command not found|is undefined' "$p" | cut -c1-130 | tr -d '|')
  [ -n "$sig" ] && printf '%s|%s\n' "$p" "$sig"
done
echo '### results_json'
find . -maxdepth 2 -name 'results.json' | sort
echo '### stat_misc'
stat -c '%n|%y|%s' sweep.log reaper.log 2>/dev/null
} > "$OUT"
echo "lines=$(wc -l < "$OUT")"
